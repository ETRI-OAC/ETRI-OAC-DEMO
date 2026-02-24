import os
import sys
import requests
import numpy as np
import time

# use pyqt5!!
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap


class STTSThread(QThread):
    # total 5 signals for 5 buttons
    tts_signal = pyqtSignal(str)
    stt_signal = pyqtSignal(str)

    def __init__(
            self,
            timeout = 1,
            stt_port = 8000, # should be modified
            tts_port = 8001, # should be modified
            ):
        super().__init__()
        # list of pyqtsignals
        self.signals = {
            'stt': self.stt_signal,
            'tts': self.tts_signal,
            'kill': None,
        }
        self.timeout = timeout
        self.default_image = np.ones((480, 640, 3), dtype=np.uint8)  # Placeholder for raw image data
        self.stt_port = stt_port
        self.tts_port = tts_port
        self.ip = "127.0.0.1"

    def fetch_stt_data(self):
        url = f"http://{self.ip}:{self.stt_port}/gui"
        current_signal = self.signals.get('stt')
        try:
            response = requests.get(url, timeout=self.timeout)
            data = response.json()
            server_message = data.get("output", "No text received")
            current_signal.emit(server_message)
        except Exception as e:
            current_signal.emit(f"Error: {str(e)}")

    def fetch_tts_data(self):
        url = f"http://{self.ip}:{self.tts_port}/gui"
        current_signal = self.signals.get('tts')
        try:
            response = requests.get(url, timeout=self.timeout)
            data = response.json()
            server_message = data.get("output", "No text received")
            current_signal.emit(server_message)
        except Exception as e:
            current_signal.emit(f"Error: {str(e)}")

    def run(self):
        while True:
            self.fetch_stt_data()
            self.fetch_tts_data()
            time.sleep(0.01)

class DemoQtWidget(QWidget):
    def __init__(
            self,
             vlm_thread,
             patrol_thread,
             user_tracking_thread,
             ):
        super().__init__()
        self.initUI()

        # placeholder image
        placeholder_path = "./placeholder.jpg"
        self.placeholder_image = QPixmap(300, 200)  # Placeholder size
        # Load placeholder image if exists
        if os.path.exists(placeholder_path):
            self.placeholder_image.load(placeholder_path)
        else:
            self.placeholder_image.fill(Qt.gray)  # Fill with gray if no image
        self.placeholder_image = self.placeholder_image.scaled(
                300, 200, # for testing, fixed size
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        # background thread - communicate with server
        if vlm_thread is not None:
            print("vlm thread received, running...")
            self.vlm_thread = vlm_thread
            self.vlm_thread.signal.connect(self.update_vlm_label)
            self.vlm_thread.start()
        if patrol_thread is not None:
            print("patrol thread received, running...")
            self.patrol_thread = patrol_thread
            self.patrol_thread.signal.connect(self.update_patrol_label)
            self.patrol_thread.start()
        if user_tracking_thread is not None:
            print("user tracking thread received, running...")
            self.user_tracking_thread = user_tracking_thread
            self.user_tracking_thread.signal.connect(self.update_user_tracking_label)
            self.user_tracking_thread.start()
        # self.stts_thread = STTSThread()
        # self.stts_thread.stt_signal.connect(self.update_stt_label)
        # self.stts_thread.tts_signal.connect(self.update_tts_label)
        # self.stts_thread.start()

        self.tts_text = ""
        print("GUI initialized")

    def initUI(self):
        # 0. main layout & title
        main_layout = QVBoxLayout()
        self.title_label = QLabel("Robot Control Console", self)
        self.title_label.setFixedSize(1000, 50) 
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # 0. components
        self.components = ['stt', 'tts', 'kill', 'vlm', 'usertracking', 'patrol']
        self.states = {comp: False for comp in self.components} # all turned off at first time
        self.state_labels = {}
        self.info_labels = {}

        # 1. text label - buttons & states
        text_button_layout = QHBoxLayout()
        self.text_buttons = ['stt', 'tts']
        for btn_name in self.text_buttons:
            part_layout = QVBoxLayout()
            # button
            btn = QPushButton(f"{btn_name} ON/OFF", self)
            btn.clicked.connect(lambda checked, name=btn_name: self.state_callback(name))
            part_layout.addWidget(btn)
            # on/off state
            state_label = QLabel(f"{btn_name}: OFF", self)
            self.state_labels[btn_name] = state_label
            part_layout.addWidget(state_label)
            # Information label
            info_label = QLabel(f"Server communication not initialized", self)
            self.info_labels[btn_name] = info_label
            part_layout.addWidget(info_label)
            text_button_layout.addLayout(part_layout)

        # 2. kill button
        kill_layout = QVBoxLayout()
        kill_btn = QPushButton('Kill', self)
        kill_btn.setFixedSize(300, 150) 
        kill_btn.clicked.connect(lambda checked, name='kill': self.kill_callback())
        kill_layout.addWidget(kill_btn)
        text_button_layout.addLayout(kill_layout)

        # 3-1. VLM label - buttons & image, text
        image_button_layout = QHBoxLayout()
        part_layout = QVBoxLayout()
        # button
        btn = QPushButton('VLM ON/OFF', self)
        btn.clicked.connect(lambda checked, name='vlm': self.state_callback(name))
        part_layout.addWidget(btn)
        # on/off state
        state_label = QLabel("VLM: OFF", self)
        self.state_labels['vlm'] = state_label
        part_layout.addWidget(state_label)
        # Information label
        image_info_label = QLabel(f"Server communication not initialized", self)
        self.info_labels['vlm_image'] = image_info_label
        text_info_label = QLabel(f"Server communication not initialized", self)
        self.info_labels['vlm_text'] = text_info_label
        part_layout.addWidget(image_info_label)
        part_layout.addWidget(text_info_label)
        image_button_layout.addLayout(part_layout)

        # 3-2. VLM label - send query
        part_layout = QVBoxLayout()
        vlm_query_btn = QPushButton('VLM Query', self)
        vlm_query_btn.setFixedSize(100, 100) 
        vlm_query_btn.clicked.connect(lambda checked, name='vlm_query': self.vlm_query_callback())
        part_layout.addWidget(vlm_query_btn)
        # label
        vlm_query_state_label = QLabel("VLM Query: OFF", self)
        self.state_labels['vlm_query'] = vlm_query_state_label
        part_layout.addWidget(vlm_query_state_label)
        image_button_layout.addLayout(part_layout)

        # 4. User Tracking & Patrol label - buttons & image
        self.image_buttons = ['usertracking', 'patrol']
        for btn_name in self.image_buttons:
            part_layout = QVBoxLayout()
            # button
            btn = QPushButton(f"{btn_name} ON/OFF", self)
            btn.clicked.connect(lambda checked, name=btn_name: self.state_callback(name))
            part_layout.addWidget(btn)
            # on/off state
            state_label = QLabel(f"{btn_name}: OFF", self)
            self.state_labels[btn_name] = state_label
            part_layout.addWidget(state_label)
            # Information label
            info_label = QLabel(f"Server communication not initialized", self)
            self.info_labels[btn_name] = info_label
            dummy_label = QLabel("") # to keep the same layout even if no image
            part_layout.addWidget(info_label)
            part_layout.addWidget(dummy_label)
            image_button_layout.addLayout(part_layout)

        # 5. set main layout
        main_layout.addLayout(text_button_layout)
        main_layout.addLayout(image_button_layout)
        self.setLayout(main_layout)
        self.setWindowTitle('Robot Control Console')
        # self.resize(300, 150)

    """ STATE CALLBACK """
    def state_callback(self, client_name):
        # update state
        self.states[client_name] = not self.states[client_name] # toggle state
        state_text = f"{client_name}: ON" if self.states[client_name] else f"{client_name}: OFF"
        self.state_labels[client_name].setText(state_text)

    """ KILL CALLBACK """
    def kill_callback(self):
        self.states = {comp: False for comp in self.components} # reset all states to off
        for label in self.state_labels.values():
            label.setText(f"{label.text().split(':')[0]}: OFF")

    """ VLM QUERY CALLBACK """
    def vlm_query_callback(self):
        if self.states['vlm']:
            self.vlm_thread.send_flag = True
            self.state_labels['vlm_query'].setText("VLM Query: TALKING...")
            time.sleep(0.1) # wait for thread to process
        else:
            self.state_labels['vlm_query'].setText("VLM Query: OFF - Turn on VLM first")

    # ====================================================================================
    """ UPDATE LABEL WITH SERVER DATA """
    def update_tts_label(self, text):
        # if state is on, update label with server text
        if self.states['tts']:
            self.info_labels['tts'].setText(text)
        else:
            self.info_labels['tts'].setText("TTS is OFF")
        self.tts_text = text

    def update_stt_label(self, text):
        if self.states['stt']:
            self.info_labels['stt'].setText(text)
        else:
            self.info_labels['stt'].setText("STT is OFF")

    # ====================================================================================
    def update_vlm_label(self, text, image):
        if self.states['vlm']:
            print("vlm thread signal received in GUI, updating label...")
            # Update with image 
            pixmap = QPixmap()
            pixmap.loadFromData(image)
            scaled_pixmap = pixmap.scaled(
                300, 200, # for testing, fixed size
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.info_labels['vlm_image'].setPixmap(scaled_pixmap)
            self.info_labels['vlm_text'].setText(text)
        else:
            self.info_labels['vlm_image'].setPixmap(self.placeholder_image)
            self.info_labels['vlm_text'].setText("VLM is OFF")
    
    # ====================================================================================
    def update_user_tracking_label(self, image):
        if self.states['usertracking']:
            # Update with image 
            pixmap = QPixmap()
            pixmap.loadFromData(image)
            scaled_pixmap = pixmap.scaled(
                300, 200, # for testing, fixed size
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.info_labels['usertracking'].setPixmap(scaled_pixmap)
        else:
            self.info_labels['usertracking'].setPixmap(self.placeholder_image)

    def update_patrol_label(self, image):
        if self.states['patrol']:
            self.patrol_thread.node.stop = False
            # image = self.patrol_thread.node.image_display # already emitted by signal
            # Update with image 
            pixmap = QPixmap()
            pixmap.loadFromData(image)
            scaled_pixmap = pixmap.scaled(
                300, 200, 
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.info_labels['patrol'].setPixmap(scaled_pixmap)
        else:
            self.patrol_thread.node.stop = True # patrol node stop flag true 
            self.info_labels['patrol'].setPixmap(self.placeholder_image) # show placeholder when patrol is off
            # or, place holder

# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     ex = DemoQtWidget()
#     ex.show()
#     # Change 2: Use exec_() for PyQt5
#     sys.exit(app.exec_())