import sys, tty, termios
import numpy as np
from dynamixel_sdk import *

DXL_MOVING_STATUS_THRESHOLD = 20
TORQUE_DISABLE = 0
TORQUE_ENABLE = 1
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
ADDR_HOMING_OFFSET = 20
ADDR_PRESENT_POSITION = 132
ADDR_POSITION_P_GAIN = 84
ADDR_BUS_WATCHDOG = 98

class pantiltManager():
    def __init__(self, SharedMemoryManager):
        self.shm = SharedMemoryManager
        self.error_status = 0
        self.position = np.zeros(2)
        self.position_raw = np.zeros(2)
        self.position_offset_deg = np.array([180.0, 45.0])
        self.axis = np.array([1.0, 1.0])

        # Dynamixel IDs
        self.DXL_YAW = 101
        self.DXL_PITCH = 102
        self.DXL_IDX = [0, 1]
        self.DXL_IDS = [self.DXL_YAW, self.DXL_PITCH]
        
        DEVICENAME = '/dev/ttyUSB0'
        PROTOCOL_VERSION = 2.0
        self.portHandler = PortHandler(DEVICENAME)
        self.packetHandler = PacketHandler(PROTOCOL_VERSION)
        
        self.LIMITS = {
            0: {"min_deg": -45.0, "max_deg": 45.0},
            1: {"min_deg": -35.0, "max_deg": 30.0},
        }

        self.open_dxl()
        self.enable_torque()

        self.set_position_p_gain(0, 400)
        self.set_position_p_gain(1, 600)

        self.sync_write = GroupSyncWrite(self.portHandler, self.packetHandler, ADDR_GOAL_POSITION, 4)
        self.bulk_read = GroupBulkRead(self.portHandler, self.packetHandler)
        self.sync_read = GroupSyncRead(self.portHandler, self.packetHandler, ADDR_PRESENT_POSITION, 4)
        self.sync_read.addParam(101)
        self.sync_read.addParam(102)
        
    def __del__(self):
        self.disable_torque()
        self.close_dxl()

    def open_dxl(self):
        BAUDRATE = 2000000
        if self.portHandler.openPort():
            print("[PANTILT MOTOR] Port opened successfully")
        else:
            print("Failed to open the port")
            quit()

        if self.portHandler.setBaudRate(BAUDRATE):
            print("[PANTILT MOTOR] Baudrate set successfully")
        else:
            print("Failed to change the baudrate")
            quit()
    
    def close_dxl(self):
        try:
            self.portHandler.closePort()
        except Exception as e:
            print(f"[PANTILT MOTOR] closePort failed: {e}")

    def enable_torque(self):
        for dxl_id in self.DXL_IDS:
            dxl_comm_result, dxl_error = self.packetHandler.write1ByteTxRx(
                self.portHandler, dxl_id, ADDR_TORQUE_ENABLE, TORQUE_ENABLE
            )
            if dxl_comm_result != COMM_SUCCESS:
                print("%s" % self.packetHandler.getTxRxResult(dxl_comm_result))
            elif dxl_error != 0:
                print("%s" % self.packetHandler.getRxPacketError(dxl_error))
            else:
                print(f"[PANTILT MOTOR] motor-{dxl_id} torque enabled")

    def disable_torque(self):
        for dxl_id in self.DXL_IDS:
            try:
                self.packetHandler.write1ByteTxRx(self.portHandler, dxl_id, ADDR_TORQUE_ENABLE, TORQUE_DISABLE)
            except Exception as e:
                print(f"[PANTILT MOTOR] Torque disable failed for motor-{dxl_id}: {e}")
    
    def set_position_p_gain(self, idx, p_gain):
        if not (0 <= p_gain <= 16383):
            raise ValueError("[PANTILT MOTOR] p_gain out of range (0~16383)")
        dxl_comm_result, dxl_error = self.packetHandler.write4ByteTxRx(self.portHandler, self.DXL_IDS[idx], ADDR_POSITION_P_GAIN, p_gain)
            
    def set_position(self):
        min_d = self.LIMITS[0]["min_deg"]
        max_d = self.LIMITS[0]["max_deg"]
        target_deg = self.shm.pantilt_goal_position[0]
        clamped_pan = max(min(target_deg, max_d), min_d)
        goal_pos_pan = self.deg_to_pos(clamped_pan * self.axis[0] + self.position_offset_deg[0])

        min_d = self.LIMITS[1]["min_deg"]
        max_d = self.LIMITS[1]["max_deg"]
        target_deg = self.shm.pantilt_goal_position[1]
        clamped_tilt = max(min(target_deg, max_d), min_d)
        goal_pos_tilt = self.deg_to_pos(clamped_tilt * self.axis[1] + self.position_offset_deg[1])

        self.syncwrite_goalpos({101: goal_pos_pan, 102: goal_pos_tilt})

    def syncwrite_goalpos(self, id_pos_dict):
        self.sync_write.clearParam()
        for dxl_id, goal in id_pos_dict.items():
            goal &= 0xFFFFFFFF
            param = bytes([
                goal & 0xFF,
                (goal >> 8) & 0xFF,
                (goal >> 16) & 0xFF,
                (goal >> 24) & 0xFF,
            ])
            if not self.sync_write.addParam(dxl_id, param):
                raise RuntimeError(f"addParam failed: {dxl_id}")

        dxl_comm_result = self.sync_write.txPacket()
        if dxl_comm_result != 0:
            raise RuntimeError(self.packetHandler.getTxRxResult(dxl_comm_result))
    
    def read_position(self):
        self.syncread_present_pos()

    def syncread_present_pos(self, ids=(101,102)):
        dxl_comm_result = self.sync_read.txRxPacket()
        if dxl_comm_result != 0:
            raise RuntimeError(self.sync_read.packetHandler.getTxRxResult(dxl_comm_result))

        for idx in self.DXL_IDX:
            if not self.sync_read.isAvailable(self.DXL_IDS[idx], ADDR_PRESENT_POSITION, 4):
                raise RuntimeError(f"Data not available: id={self.DXL_IDS[idx]}")
            dxl_present_position = self.sync_read.getData(self.DXL_IDS[idx], ADDR_PRESENT_POSITION, 4)
            self.position_raw[idx] = self.pos_to_deg(dxl_present_position)   # 절대 각도(오프셋 포함)
            self.position[idx] = self.axis[idx] * (self.position_raw[idx] - self.position_offset_deg[idx])
            self.shm.pantilt_position[idx] = self.position[idx]

    def reset_error(self, reboot: bool = True, clear_bus_watchdog: bool = True,
                    off_time_sec: float = 0.2, torque_on_after: bool = True):
        self.disable_torque()
        time.sleep(max(0.0, off_time_sec))

        if clear_bus_watchdog:
            for dxl_id in self.DXL_IDS:
                self.packetHandler.write1ByteTxRx(self.portHandler, dxl_id, ADDR_BUS_WATCHDOG, 0)

        if reboot:
            for dxl_id in self.DXL_IDS:
                self.packetHandler.reboot(self.portHandler, dxl_id)
            time.sleep(0.3)  # reboot 직후 짧게 대기

        if torque_on_after:
            self.enable_torque()

    def deg_to_pos(self, deg):
        return int(deg * 4096 / 360)

    def pos_to_deg(self, pos):
        return pos * 360 / 4096