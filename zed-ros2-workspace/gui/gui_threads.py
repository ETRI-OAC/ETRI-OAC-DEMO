import os
import sys
import requests
import numpy as np

# use pyqt5!!
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap


class DemoQtWidget(QWidget):
    def __init__(
            self,
             vlm_thread,
             patrol_thread,
             user_tracking_thread,
             ):
        super().__init__()
        self.initUI()

        # background thread - communicate with server
        self.vlm_thread = vlm_thread
        self.patrol_thread = patrol_thread
        self.user_tracking_thread = user_tracking_thread
        self.vlm_thread.signal.connect(self.update_vlm_label)
        self.patrol_thread.signal.connect(self.update_patrol_label)
        self.user_tracking_thread.signal.connect(self.update_user_tracking_label)

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
        self.background_thread.start()
        self.node_thread = node_thread
        self.node_thread.start()

        self.tts_text = ""

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

        # 4. kill button
        kill_layout = QVBoxLayout()
        kill_btn = QPushButton('Kill', self)
        kill_btn.setFixedSize(300, 150) 
        kill_btn.clicked.connect(lambda checked, name='kill': self.kill_callback())
        kill_layout.addWidget(kill_btn)
        text_button_layout.addLayout(kill_layout)

        # 2. VLM label - buttons & image, text
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

        # 3. User Tracking & Patrol label - buttons & image
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

    def update_vlm_label(self, data):
        if self.states['vlm']:
            # Update with image 
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            scaled_pixmap = pixmap.scaled(
                300, 200, # for testing, fixed size
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.info_labels['vlm_image'].setPixmap(scaled_pixmap)
            self.info_labels['vlm_text'].setText(self.tts_text)
        else:
            self.info_labels['vlm_image'].setPixmap(self.placeholder_image)
            self.info_labels['vlm_text'].setText("VLM is OFF")
    
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
            # Update with image 
            pixmap = QPixmap()
            pixmap.loadFromData(image)
            scaled_pixmap = pixmap.scaled(
                300, 200, # for testing, fixed size
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.info_labels['patrol'].setPixmap(scaled_pixmap)
        else:
            self.info_labels['patrol'].setPixmap(self.placeholder_image) # show placeholder when patrol is off
            # or, place holder

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DemoQtWidget()
    ex.show()
    # Change 2: Use exec_() for PyQt5
    sys.exit(app.exec_())