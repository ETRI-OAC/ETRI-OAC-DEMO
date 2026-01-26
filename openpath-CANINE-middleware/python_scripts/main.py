import rclpy
import threading
import time
from canineStruct import Command, CanineFSM
from rosCommunication import ROSCommunication
from pantiltManager import pantiltManager
from zedManager import zedManager
from sharedMemory import SharedMemoryManager
from colorama import Fore, Style
import math

shm = SharedMemoryManager()
cam = zedManager(shm)

def rosCommunicationThread(args=None):
    rclpy.init(args=args)
    node = ROSCommunication(shm)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

def userCommandThread(args=None):
    time.sleep(1)
    while shm.middleware_connected == False:
        print(Fore.RED + "[PY_MAIN] Failed to communicate with middleware." + Style.RESET_ALL)
        time.sleep(1)
    
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] CANINE FSM:" ,CanineFSM(shm.fsm_state),Style.RESET_ALL)

    shm.cmd.reference_base_velocity = [0.1, 0.0]  # float values
    time.sleep(3)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] FSM:\t",CanineFSM(shm.fsm_state),Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] body vel:\t",shm.body_base_velocity,Style.RESET_ALL)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] base quat:\t",shm.global_base_quaternion,Style.RESET_ALL)

    time.sleep(1)
    shm.cmd.reference_base_velocity = [0.0, 0.1]  
    time.sleep(1)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] body vel:\t",shm.body_base_velocity,Style.RESET_ALL)

    shm.cmd.reference_base_velocity = [0.0, 0.0]  
    shm.cmd.reference_base_yaw_velocity = -0.5
    time.sleep(1)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] body vel:\t",shm.body_base_velocity,Style.RESET_ALL)

    shm.cmd.reference_base_yaw_velocity = 0.0
    time.sleep(4)
    print(Fore.LIGHTBLUE_EX,time.strftime("%H:%M:%S", time.gmtime(shm.local_time)),"[PY_MAIN] USER CONTROL THREAD END",Style.RESET_ALL)




def pantiltMotorControlThread(args=None):
    pantilt = pantiltManager(shm)
    pantilt.reset_error()
    local_time = 0
    while True:
        pantilt.read_position()
        # print("pantilt_yaw: ",shm.pantilt_position[0])
        # print("pantilt_goal_yaw: ",shm.pantilt_goal_position[0])
        # print("pantilt_pitch: ",shm.pantilt_position[1])
        # print("pantilt_goal_pitch: ",shm.pantilt_goal_position[1])
        shm.pantilt_goal_position[0] = 45.0 * math.sin(2 * math.pi * 0.5 * local_time)
        shm.pantilt_goal_position[1] = 30.0 * math.sin(2 * math.pi * 0.5 * local_time)
        pantilt.set_position()
        local_time += 0.02
        time.sleep(0.01) 

cam.get_image()  # Save images to shm.left_image[0], shm.right_image[0]
cam.save_image() # Save images to zzed_image directory

thread_ros_communication = threading.Thread(target=rosCommunicationThread)
thread_ros_communication.start()
thread_user = threading.Thread(target=userCommandThread)
thread_user.start()
thread_pantilt = threading.Thread(target=pantiltMotorControlThread)
thread_pantilt.start()