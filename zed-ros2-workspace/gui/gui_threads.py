import os
import sys
import requests
import numpy as np
import time
import cv2

# use pyqt5!!
# What's modified: Qcombo added
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QFont, QImage

class STTSThread(QThread):
    # total 5 signals for 5 buttons
    tts_signal = pyqtSignal(str)
    stt_signal = pyqtSignal(str)

    def __init__(
            self,
            timeout = 1,
            stt_port = 8001,
            tts_port = 8002,
            ):
        super().__init__()
        self.timeout = timeout
        self.stt_port = stt_port
        self.tts_port = tts_port
        self.ip = "127.0.0.1"

    def fetch_stt_data(self):
        url = f"http://{self.ip}:{self.stt_port}/gui"
        try:
            response = requests.get(url, timeout=self.timeout)
            data = response.json()
            server_message = data.get("output", "No text received")
            self.stt_signal.emit(server_message)
        except Exception as e:
            self.stt_signal.emit(f"Error: {str(e)}")

    def fetch_tts_data(self):
        url = f"http://{self.ip}:{self.tts_port}/gui"
        try:
            response = requests.get(url, timeout=self.timeout)
            data = response.json()
            server_message = data.get("output", "No text received")
            self.tts_signal.emit(server_message)
        except Exception as e:
            self.tts_signal.emit(f"Error: {str(e)}")

    def run(self):
        while True:
            self.fetch_stt_data()
            self.fetch_tts_data()
            time.sleep(0.1)

class DemoQtWidget(QWidget):
    def __init__(
            self,
             vlm_thread,
             patrol_thread,
             usertracking_thread,
             ):
        super().__init__()

        # placeholder image
        placeholder_path = "./placeholder.jpg"
        self.placeholder_image = QPixmap(300, 250)  # Placeholder size
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

        # what's modified: body ids initialize 
        self.body_ids = ["-1"]
        self.target_id = -1
        self.target_id_update_flag = False
        # UI initialization
        self.initUI()

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
        if usertracking_thread is not None:
            print("user tracking thread received, running...")
            self.usertracking_thread = usertracking_thread
            self.usertracking_thread.signal.connect(self.update_user_tracking_label)
            self.usertracking_thread.start()
        self.stts_thread = STTSThread()
        self.stts_thread.stt_signal.connect(self.update_stt_label)
        self.stts_thread.tts_signal.connect(self.update_tts_label)
        self.stts_thread.start()

        

        # set fonts 
        self.set_fonts(hangul_label_names=['stt', 'tts', 'vlm_text'])
        # vlm control flag 
        self.allow_vlm_ctrl = False
        print("GUI initialized")

    def initUI(self):
        # 0. main layout & title
        main_layout = QVBoxLayout()
        self.title_label = QLabel("Robot Control Console", self)
        self.title_label.setFixedSize(1000, 50) 
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # 0. components
        # self.components = ['stt', 'tts', 'kill', 'vlm', 'usertracking', 'patrol']
        self.components = ['vlm', 'usertracking', 'patrol']
        self.states = {comp: False for comp in self.components} # all turned off at first time
        self.state_labels = {}
        self.info_labels = {}

        # 1. text label - buttons & states
        text_button_layout = QHBoxLayout()
        self.stt_tts = ['stt', 'tts']
        for name in self.stt_tts:
            part_layout = QVBoxLayout()
            # what's modified: button is deleted
            # on/off state
            state_label = QLabel(f"{name} - output is: ", self)
            self.state_labels[name] = state_label
            part_layout.addWidget(state_label)
            # Information label
            info_label = QLabel(f"Server communication not initialized", self)
            self.info_labels[name] = info_label
            part_layout.addWidget(info_label)
            text_button_layout.addLayout(part_layout)

        # 2. vlm control & kill button
        vlm_cmd_and_kill_layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        # vlm control button
        vlm_ctrl_btn = QPushButton('Allow VLM Control', self)
        vlm_ctrl_btn.setFixedSize(150, 100) 
        vlm_ctrl_btn.clicked.connect(lambda checked, name='vlm_control': self.vlm_control_callback())
        button_layout.addWidget(vlm_ctrl_btn)
        # kill button 
        kill_btn = QPushButton('Kill', self)
        kill_btn.setFixedSize(150, 100) 
        kill_btn.clicked.connect(lambda checked, name='kill': self.kill_callback())
        button_layout.addWidget(kill_btn)
        vlm_cmd_and_kill_layout.addLayout(button_layout)
        # label
        self.state_labels['vlm_control_and_kill'] = QLabel("GUI is controlling the robot", self)
        vlm_cmd_and_kill_layout.addWidget(self.state_labels['vlm_control_and_kill'])
        text_button_layout.addLayout(vlm_cmd_and_kill_layout)

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
        image_info_label.setPixmap(self.placeholder_image)
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
        vlm_query_state_label = QLabel("Send VLM Query", self)
        self.state_labels['vlm_query'] = vlm_query_state_label
        # what's modified: word wrap & width fixing
        self.state_labels['vlm_query'].setWordWrap(True)
        self.state_labels['vlm_query'].setFixedWidth(200)
        part_layout.addWidget(vlm_query_state_label)
        image_button_layout.addLayout(part_layout)

        # 4. User Tracking & Patrol label - buttons & image
        self.image_buttons = ['usertracking', 'patrol']
        part_layout = QVBoxLayout()
        # button
        btn = QPushButton(f"usertracking ON/OFF", self)
        btn.clicked.connect(lambda checked, name='usertracking': self.state_callback(name))
        part_layout.addWidget(btn)
        # on/off state
        state_label = QLabel(f"usertracking: OFF", self)
        self.state_labels['usertracking'] = state_label
        part_layout.addWidget(state_label)
        # Information label
        info_label = QLabel(f"Server communication not initialized", self)
        info_label.setPixmap(self.placeholder_image)
        self.info_labels['usertracking'] = info_label
        # what's modified: combo scroll added
        # track id set with combo
        self.combo = QComboBox()
        self.combo.addItems(self.body_ids)
        self.combo.currentIndexChanged.connect(self.update_tracking_id_callback)
        # label
        track_id_label = QLabel("Tracking: 0", self)
        self.state_labels["track_id"] = track_id_label
        part_layout.addWidget(self.combo)
        part_layout.addWidget(info_label)
        image_button_layout.addLayout(part_layout)

        # 5. User Tracking & Patrol label - buttons & image
        part_layout = QVBoxLayout()
        btn = QPushButton(f"patrol ON/OFF", self)
        btn.clicked.connect(lambda checked, name='patrol': self.state_callback(name))
        part_layout.addWidget(btn)
        state_label = QLabel(f"patrol: OFF", self)
        self.state_labels['patrol'] = state_label
        part_layout.addWidget(state_label)
        # Information label
        info_label = QLabel(f"Server communication not initialized", self)
        info_label.setPixmap(self.placeholder_image)
        self.info_labels['patrol'] = info_label
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
        if not self.allow_vlm_ctrl:
            self.states[client_name] = not self.states[client_name] # toggle state
            state_text = f"{client_name}: ON" if self.states[client_name] else f"{client_name}: OFF"
            self.state_labels[client_name].setText(state_text)

    """ KILL CALLBACK """
    def kill_callback(self):
        self.states = {comp: False for comp in self.components} # reset all states to off
        for label in self.state_labels.values():
            label.setText(f"{label.text().split(':')[0]}: OFF")
        self.state_labels['vlm_control_and_kill'].setText("All systems killed")

    """ VLM QUERY CALLBACK """
    def vlm_query_callback(self):
        if self.states['vlm'] and self.vlm_thread.send_flag == False:
            self.vlm_thread.send_flag = True
            self.state_labels['vlm_query'].setText("VLM Query: TALKING...")
            time.sleep(0.1) # wait for thread to process
        else:
            self.state_labels['vlm_query'].setText("VLM Query: OFF - Turn on VLM first")

    """ VLM CONTROL CALLBACK: ALLOW VLM TO CONTROL """
    def vlm_control_callback(self): 
        self.allow_vlm_ctrl = not self.allow_vlm_ctrl
        if self.allow_vlm_ctrl:
            # set patrol and usertracking state false
            self.states['patrol'] = False
            self.states['usertracking'] = False
            self.states['vlm'] = True
            self.state_labels['patrol'].setText("patrol: OFF")
            self.state_labels['usertracking'].setText("usertracking: OFF")
            self.state_labels['vlm'].setText("vlm: ON")
            self.state_labels['vlm_control_and_kill'].setText("VLM is controlling the robot")
        else:
            self.states['patrol'] = False
            self.states['usertracking'] = False
            self.states['vlm'] = False
            self.state_labels['patrol'].setText("patrol: OFF")
            self.state_labels['usertracking'].setText("usertracking: OFF")
            self.state_labels['vlm'].setText("vlm: OFF")
            self.state_labels['vlm_control_and_kill'].setText("GUI is controlling the robot")

    """ UPDATE TRACKING ID CALLBACK """
    # what's modified: update with combo
    def update_tracking_id_callback(self):
        if self.target_id_update_flag:
            selected_idx = self.combo.currentText()
            if selected_idx == "":
                selected_idx = -1
                self.usertracking_thread.client.target_id = selected_idx
                self.target_id = selected_idx
            else:
                selected_idx = int(selected_idx)
                self.usertracking_thread.client.target_id = selected_idx
                self.target_id = selected_idx


    # ====================================================================================
    """ UPDATE TTS - STT INFO WITH STT THREAD """
    def update_tts_label(self, text):
        self.info_labels['tts'].setText(text)

    def update_stt_label(self, text):
        self.info_labels['stt'].setText(text)

    # ====================================================================================
    def update_vlm_label(self, text, image, patrol_flag, usertracking_flag):
        if self.states['vlm']:
            print("vlm thread signal received in GUI, updating label...")
            print("image shape in vlm update:", image.shape)
            # Update with image 
            scaled_pixmap = zed_image_to_qpixmap(image)
            self.info_labels['vlm_image'].setPixmap(scaled_pixmap)
            self.info_labels['vlm_text'].setText(text)

            # patrol - usertracking turn on/off
            if self.allow_vlm_ctrl == True:
                if patrol_flag == True:
                    self.states['patrol'] = True
                    self.state_labels['patrol'].setText("patrol: ON")
                else:
                    self.states['patrol'] = False
                    self.state_labels['patrol'].setText("patrol: OFF")
                if usertracking_flag == True:
                    self.states['usertracking'] = True
                    self.state_labels['usertracking'].setText("usertracking: ON")
                else:
                    self.states['usertracking'] = False
                    self.state_labels['usertracking'].setText("usertracking: OFF")
        else:
            self.info_labels['vlm_image'].setPixmap(self.placeholder_image)
            self.info_labels['vlm_text'].setText("VLM is OFF")
        self.vlm_thread.client.warning_flag = False # reset warning flag after updating label
    
    # ====================================================================================
    def update_user_tracking_label(self, body_ids, image):
        if self.states['usertracking']:

            # what's modified: update body id, update combo
            self.target_id_update_flag = False
            self.body_ids = [str(i) for i in body_ids]
            self.body_ids = ["", "-1"] + self.body_ids
            self.combo.clear() 
            self.combo.addItems(self.body_ids)
            self.state_labels["track_id"].setText(f"track id: {self.target_id}")
            self.target_id_update_flag = True
            
            # what's modified: warning flag on to send pre-defined flags
            try:
                self.vlm_thread.client.warning_flag = True
            except:
                print("warning flag not sent")
            # Update with image 
            scaled_pixmap_usertracking = zed_image_to_qpixmap(image)
            self.info_labels['usertracking'].setPixmap(scaled_pixmap_usertracking)
            # what's modified: resume flag no update
            if self.usertracking_thread.client.navigation_resume_flag == False:
                self.usertracking_thread.client.navigation_resume_flag = True
        else:
            self.body_ids = ["-1"]
            self.info_labels['usertracking'].setPixmap(self.placeholder_image)
            self.usertracking_thread.client.navigation_resume_flag = False # stop navigation when usertracking is off

    def update_patrol_label(self, image):
        if self.states['patrol']:
            self.patrol_thread.client.stop = False
            scaled_pixmap = zed_image_to_qpixmap(image)
            self.info_labels['patrol'].setPixmap(scaled_pixmap)
        else:
            self.patrol_thread.client.stop = True # patrol node stop flag true 
            self.info_labels['patrol'].setPixmap(self.placeholder_image) # show placeholder when patrol is off
            # or, place holder
    
    # ====================================================================================
    def set_fonts(self, hangul_label_names = []):
        for label_name in hangul_label_names:
            if label_name in self.info_labels:
                self.info_labels[label_name].setFont(QFont("NanumGothic", 10))
                self.info_labels[label_name].setWordWrap(True)
                self.info_labels[label_name].setFixedWidth(200)


""" UTILS: ZED TO QIMAGE """
def zed_image_to_qpixmap(zed_image):
    height, width, channel = zed_image.shape
    bytes_per_line = channel * width
    zed_image = cv2.cvtColor(zed_image, cv2.COLOR_BGR2RGB) # Convert BGR to RGB
    qimg = QImage(zed_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
    qpixmap = QPixmap.fromImage(qimg)
    qpixmap_scaled = qpixmap.scaled(300, 250)
    return qpixmap_scaled

# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     ex = DemoQtWidget()
#     ex.show()
#     # Change 2: Use exec_() for PyQt5
#     sys.exit(app.exec_())