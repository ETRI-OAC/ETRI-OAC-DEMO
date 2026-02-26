# add higher directory path
import sys
import os
import cv2

import base64
import json
import time
import requests
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import time
import numpy as np
from zed_wrapper.body_tracking_visualizer import visualize_bodies_2d

# GUI
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap

# ros2 
import rclpy
from rclpy.node import Node

# import clients
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from clients.stt_client import STTClient
from clients.tts_client import TTSClient
from clients.zed_client import ZedClient
from clients.face_recognition_client import FaceRecognitionClient
# import threads 
from _20_vlm_gui import VLLMClient, VLLMThread
from _21_patrol_gui import faceIdentificationWithNav, PatrolThread
from _22_usertracking_gui import humanTracking, UsertrackingThread
# import gui widget
from gui.gui_threads import DemoQtWidget


def main():
    # 0. run qt and ros2 
    app = QApplication(sys.argv)
    rclpy.init()
    # 1. basic clients 
    stt_client = STTClient()
    tts_client = TTSClient()
    zed_client = ZedClient()
    face_recognition_client = FaceRecognitionClient()
    # 2. vlm, patrol, usertracking clients
    vllm_client = VLLMClient(
        api_url = "http://localhost:8000",
        stt_client = stt_client,
        tts_client = tts_client,
        zed_client=zed_client
    )
    patrol_client = faceIdentificationWithNav(
        zed_client,
        tts_client,
        face_recognition_client,
        use_navigation= True,
        use_audio=True
        )
    usertracking_client = humanTracking(
        zed_client = zed_client,
        tts_client = tts_client
    )
    # 3. threads
    vlm_thread = VLLMThread(vllm_client)
    patrol_thread = PatrolThread(patrol_client)
    usertracking_thread = UsertrackingThread(usertracking_client)
    qt_widget = DemoQtWidget(
        vlm_thread=vlm_thread,
        patrol_thread=patrol_thread,
        usertracking_thread=usertracking_thread
    )
    qt_widget.show()
    app.exec_()
    rclpy.shutdown()

if __name__ == "__main__":
    main()