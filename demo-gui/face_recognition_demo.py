"""
Face Recognition Demo
- Camera feed with skeleton + face bbox overlay (PyQt5 window, no cv2.namedWindow)
- Face recognition via Hailo inference server
- Pan-tilt servo tracking via ROS 2
"""
import sys
import os
import cv2
import time
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'oak-camera'))

from clients.zed_client import ZedClient
from clients.face_recognition_client import FaceRecognitionClient
from clients.tts_client import TTSClient
from clients.body_tracking_visualizer import visualize_bodies_2d
from utils.pid import PIDControllerClass

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


def bgr_to_pixmap(image: np.ndarray) -> QPixmap:
    h, w, ch = image.shape
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    q_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(q_img)


class FaceRecognitionNode(Node):
    def __init__(self, zed_client: ZedClient, face_client: FaceRecognitionClient, tts_client: TTSClient):
        super().__init__('face_recognition_demo')

        self.zed_client = zed_client
        self.face_client = face_client
        self.tts_client = tts_client

        self.image_width = zed_client.image_shape[1]
        self.image_height = zed_client.image_shape[0]
        self.center_cam = np.array([self.image_width / 2, self.image_height / 2])

        # Pan-tilt
        self.pantilt_state = [0.0, 0.0]
        self.pantilt_command = [0.0, 0.0]
        self.pid = PIDControllerClass(k_p=30, k_d=1, out_min=-30, out_max=30, dim=1, out_alpha=0.5)
        self.pid.reset()
        self.t_s = time.time()

        # Face recognition state
        self.face_id_memory = {}      # {body_id: name}
        self.recognized_names = set()
        self.target_id = 0
        self.target_id_prev = 0
        self.face_recognition_cnt = 0
        self.not_unknown_cnt = 0
        self.not_looking_cnt = 0
        self.recognition_name = None

        # Latest frame for Qt display
        self.image_display = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)
        self.status_text = "초기화 중..."
        self.tts_log = []  # recent TTS messages for GUI display
        self.timer_flag = False

        # ROS 2
        self.sub_pantilt = self.create_subscription(
            Float64MultiArray, 'pantilt_state', self._pantilt_cb, 10)
        self.pub_pantilt = self.create_publisher(Float64MultiArray, 'pantilt_command', 10)
        self.timer = self.create_timer(0.033, self._tick)  # ~30 Hz

    # ── ROS callbacks ──────────────────────────────────────────────────────────

    def _pantilt_cb(self, msg):
        self.pantilt_state = list(msg.data)

    def _tick(self):
        image = self.zed_client.grab_image()
        if image is None:
            return
        disp = image.copy()
        bodies = self.zed_client.grab_bodies()

        if bodies:
            disp = self._overlay_skeletons(disp, bodies)
            bodies_close = self._filter_bodies(bodies, max_dist=3.0)

            # Choose target: first body not yet recognised
            untreated = [b for b in bodies_close if b['id'] not in self.face_id_memory]
            if untreated:
                self.target_id = untreated[0]['id']
            # Reset counters when target changes
            if self.target_id != self.target_id_prev:
                self.target_id_prev = self.target_id
                self.face_recognition_cnt = 0
                self.not_unknown_cnt = 0
                self.not_looking_cnt = 0
                self.recognition_name = None

            for body in bodies_close:
                face_img, bbox = self._crop_face(image, body)
                if body['id'] == self.target_id:
                    if face_img is not None:
                        looking = self._is_looking(body)
                        if looking:
                            result, _ = self.face_client.recognize(face_img, measure_time=False)
                            name, sim = result['name'], result['similarity']
                            self._draw_face_result(disp, bbox, body['id'], name, sim, "looking")
                            self.not_looking_cnt = 0
                            self.face_recognition_cnt += 1
                            if name != "Unknown":
                                self.recognition_name = self.recognition_name or name
                                self.not_unknown_cnt += 1
                            if self.face_recognition_cnt > 30:
                                if self.not_unknown_cnt > 5:
                                    final = self.recognition_name
                                    self.recognized_names.add(final)
                                    tts_msg = f"{final} 님 안녕하세요."
                                else:
                                    final = "Unknown"
                                    tts_msg = "등록되지 않은 인물입니다."
                                self.tts_client.speak(text=tts_msg)
                                self._add_tts_log(tts_msg)
                                self.face_id_memory[body['id']] = final
                                self.status_text = f"인식 완료: {final}"
                                self.target_id += 1
                                self.face_recognition_cnt = 0
                                self.not_unknown_cnt = 0
                                self.recognition_name = None
                        else:
                            self._draw_face_result(disp, bbox, body['id'], "인식 중...", 0.0, "not looking")
                            self.not_looking_cnt += 1
                            if self.not_looking_cnt > 60:
                                tts_msg = "카메라를 응시해주세요."
                                self.tts_client.speak(text=tts_msg)
                                self._add_tts_log(tts_msg)
                                self.not_looking_cnt = 0
                                self.face_recognition_cnt = 0
                                self.not_unknown_cnt = 0
                                self.recognition_name = None
                    self._move_pantilt(body)
                else:
                    known_name = self.face_id_memory.get(body['id'], "Not recognized")
                    if bbox is not None:
                        self._draw_face_bbox(disp, bbox, body['id'], known_name)

            if not bodies_close:
                self.status_text = "대기 중 (근거리 인물 없음)"
        else:
            self.status_text = "대기 중 (인물 감지 안됨)"

        self.image_display = disp
        self.full_status = self._build_status()
        self.timer_flag = True

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _add_tts_log(self, msg):
        self.tts_log.append(msg)
        if len(self.tts_log) > 10:
            self.tts_log = self.tts_log[-10:]

    def _build_status(self):
        lines = [f"[상태] {self.status_text}", ""]
        if self.face_id_memory:
            lines.append("[인식 결과]")
            for bid, name in self.face_id_memory.items():
                lines.append(f"  ID {bid}: {name}")
            lines.append("")
        if self.tts_log:
            lines.append("[음성 안내]")
            for msg in self.tts_log:
                lines.append(f"  🔊 {msg}")
        return "\n".join(lines)

    def _filter_bodies(self, bodies, max_dist=3.0):
        return [b for b in bodies
                if b['head_position'][0]**2 + b['head_position'][1]**2 < max_dist**2]

    def _crop_face(self, image, body):
        bbox2d = np.array(body['head_bounding_box_2d'])
        x1, x2 = int(bbox2d[0][0]), int(bbox2d[1][0])
        y1 = int(bbox2d[1][1]) - 50
        y2 = int(bbox2d[2][1])
        x1 = np.clip(x1, 1, self.image_width - 1)
        x2 = np.clip(x2, 1, self.image_width - 1)
        y1 = np.clip(y1, 1, self.image_height - 1)
        y2 = np.clip(y2, 1, self.image_height - 1)
        face = image[y1:y2, x1:x2]
        if face.size == 0:
            return None, None
        return face, np.array([x1, y1, x2, y2])

    def _is_looking(self, body, threshold=20):
        q = body['head_orientation']
        sin_y = 2 * (q[3]*q[2] + q[0]*q[1])
        cos_y = 1 - 2 * (q[1]**2 + q[2]**2)
        yaw = np.arctan2(sin_y, cos_y)
        return abs(yaw) > np.deg2rad(180 - threshold)

    def _move_pantilt(self, body):
        face_x = body['keypoints_2d'][0][0]
        err_x = -(face_x - self.center_cam[0]) / self.center_cam[0]
        t = time.time() - self.t_s
        self.pid.update_with_error(t_curr=t, err_curr=err_x)
        cmd = list(self.pantilt_state)
        cmd[0] += self.pid.out()
        self.pantilt_command = cmd
        msg = Float64MultiArray()
        msg.data = self.pantilt_command
        self.pub_pantilt.publish(msg)

    def _overlay_skeletons(self, image, bodies):
        return visualize_bodies_2d(image, bodies, body_format=34)

    def _draw_face_result(self, image, bbox, body_id, name, similarity, info):
        x1, y1, x2, y2 = bbox
        label = f"ID:{body_id} {name} ({similarity:.2f}) [{info}]"
        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.rectangle(image, (x1, y2 + 2), (x1 + tw + 8, y2 + th + 12), (0, 0, 255), -1)
        cv2.putText(image, label, (x1 + 4, y2 + th + 6), font, scale, (255, 255, 255), thick, cv2.LINE_AA)

    def _draw_face_bbox(self, image, bbox, body_id, name):
        x1, y1, x2, y2 = bbox
        color = (0, 255, 0) if name not in ("Not recognized", "Unknown") else \
                (0, 165, 255) if name == "Unknown" else (0, 255, 255)
        label = f"ID:{body_id} {name}"
        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.rectangle(image, (x1, y2 + 2), (x1 + tw + 8, y2 + th + 12), color, -1)
        cv2.putText(image, label, (x1 + 4, y2 + th + 6), font, scale, (0, 0, 0), thick, cv2.LINE_AA)


class FaceRecognitionThread(QThread):
    frame_signal = pyqtSignal(object)   # numpy BGR image
    status_signal = pyqtSignal(str)

    def __init__(self, node: FaceRecognitionNode):
        super().__init__()
        self.node = node

    def run(self):
        while True:
            rclpy.spin_once(self.node, timeout_sec=0.02)
            if self.node.timer_flag:
                self.node.timer_flag = False
                self.frame_signal.emit(self.node.image_display.copy())
                self.status_signal.emit(self.node.full_status)


class FaceRecognitionWindow(QWidget):
    def __init__(self, node: FaceRecognitionNode):
        super().__init__()
        self.setWindowTitle("Face Recognition Demo")

        # Camera view
        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(960, 540)

        # Status panel
        self.status_label = QLabel("초기화 중...")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.status_label.setStyleSheet("font-size: 16px; padding: 10px;")
        self.status_label.setMinimumWidth(300)
        self.status_label.setWordWrap(True)

        # Layout
        h = QHBoxLayout()
        h.addWidget(self.camera_label, stretch=3)
        h.addWidget(self.status_label, stretch=1)
        self.setLayout(h)

        # Thread
        self.thread = FaceRecognitionThread(node)
        self.thread.frame_signal.connect(self._update_frame)
        self.thread.status_signal.connect(self.status_label.setText)
        self.thread.start()

    def _update_frame(self, image: np.ndarray):
        pixmap = bgr_to_pixmap(image)
        scaled = pixmap.scaled(
            self.camera_label.width(), self.camera_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.camera_label.setPixmap(scaled)


def main():
    rclpy.init()
    zed_client = ZedClient()
    if zed_client.shm_image_block is None:
        print("[ERROR] Camera shared memory not available. Is oak_server running?")
        rclpy.shutdown()
        sys.exit(1)

    face_client = FaceRecognitionClient()
    tts_client = TTSClient()
    node = FaceRecognitionNode(zed_client, face_client, tts_client)

    app = QApplication(sys.argv)
    window = FaceRecognitionWindow(node)
    window.show()
    ret = app.exec_()

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(ret)


if __name__ == "__main__":
    main()
