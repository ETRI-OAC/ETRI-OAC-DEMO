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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from clients.stt_client import STTClient
from clients.tts_client import TTSClient
from clients.zed_client import ZedClient

# GUI
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from gui.gui_threads import DemoQtWidget


instruction_two_sentence = "지금부터 모든 응답은 두 문장 이내로 해줘."
patrol_instruction = "앞으로 '순찰을 시작해줘'이라는 명령이 들어오면, '순찰을 시작하겠습니다'라고 한문장으로 대답해줘. 그리고 '순찰 종료'라는 명령이 들어오면, '순찰을 종료하겠습니다'라고 한문장으로 대답해줘."
instruction_usertracking = "앞으로 '나를 따라와'이라는 명령이 들어오면, '네, 따라가겠습니다'라고 한문장으로 대답해줘. 그리고 '그만 따라와'라는 명령이 들어오면, '네, 멈추겠습니다'라고 한문장으로 대답해줘."
instruction_require_answer = "이제 질문에 대답해줘."

instruc = {}
instruc["default"] = instruction_two_sentence + patrol_instruction + instruction_usertracking
instruc["prefix"] = instruction_two_sentence
instruc["hello"] = "이 이미지에서 무엇을 보고 있는지 알려줘."
instruc["car"] = "이 이미지에서 차가 몇 대 있는지 알려줘."
instruc["person"] = "이 이미지에서 사람은 몇 명인지 알려줘."

instruc["instruction_patrol"] = "앞으로 '순찰 시작'이라는 명령이 들어오면, '순찰을 시작하겠습니다'라고 대답해줘. 그리고 '순찰 종료'라는 명령이 들어오면, '순찰을 종료하겠습니다'라고 대답해줘."
instruc["initialize_patrol"] = "순찰 시작"
instruc["terminate_patrol"] = "순찰 종료"

# what's modified: warning instruction 
instruc["user_track_warning"] = "지금 보고 있는 이미지에 차량이나 자전거가 있다면, '위험, 전방에 차량이 있습니다.' 혹은 '위험, 전방에 자전거가 있습니다.' 라고 답해줘. 만약 없을 경우에는, 아무 대답도 하지 마."


""" UTILS """
# 1. encode image
def encode_image(image: np.ndarray) -> str:
    # encode self.image to base64 string
    _, buffer = cv2.imencode(".jpg", image)
    return base64.b64encode(buffer).decode('utf-8')

""" VLLM CLIENT"""
class VLLMClient():
    """
    VLLM Client
    """
    
    def __init__(
            self,
            api_url: str = "http://localhost:8000",
            model: str = "cpatonn/Qwen3-VL-4B-Instruct-AWQ-4bit",
            max_tokens: int = 512,
            temperature: float = 0.7,
            stt_client = None,
            tts_client = None,
            zed_client = None
            ):

        # initialize vlm
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # stt, tts, zed clients 
        self.stt_client = stt_client
        self.tts_client = tts_client
        self.zed_client = zed_client
        self.image = self.zed_client.grab_image()

    def query(self, prompt: str, measure_time: bool = False) -> Tuple[Dict[str, Any], Optional[float]]:
        base64_image = encode_image(self.image)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        start_time = time.time() if measure_time else None
        response = requests.post(
            f"{self.api_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        response_json = response.json()    
        elapsed_time = (time.time() - start_time) if measure_time else None
        return response_json, elapsed_time

    def warmup(self, prompt: str, count: int = 10):
        print(f"Warming up {count} times...")
        warmup_start = time.time()
        for i in range(count):
            try:
                self.query(prompt, measure_time=False)
                print(f"[{i+1}/{count}] Warmup complete", end='\r')
            except requests.exceptions.ConnectionError:
                print("Could not connect to vLLM Server.")
            except requests.exceptions.HTTPError as e:
                print(f"http error: {e}")
            except Exception as e:
                print(f"failed warmup at {i+1} iteration: {e}")
                return
        warmup_total_time = time.time() - warmup_start
        print(f"Warpup done, total {warmup_total_time:.2f}s")
        print("-" * 60)

    def get_vlm_response(self, prompt: str = None, use_audio = False, use_prefix = True):
        # stt 
        if prompt is None:
            print("Listening for STT input...")
            response, _ = self.stt_client.transcribe_from_mic(duration_sec=5)
            prompt = response.get("text", "")
            print(f"STT result for VLM query: {prompt}")
        else: 
            print(f"Using provided prompt: {prompt}")
        # prefix
        if use_prefix:
            prompt = instruc["prefix"] + " " + prompt
        # zed
        self.image = self.zed_client.grab_image()
        # vlm query 
        response, elapsed_time = self.query(prompt, measure_time=True)

        if "choices" in response and len(response["choices"]) > 0:
            answer = response["choices"][0]["message"]["content"]
            print("-" * 60)
            print(f"Response received, answer: {answer}")
            print("-" * 60)
            if use_audio:
                self.tts_client.speak(answer)
            return answer, self.image
        else:
            print("Unexpected response format.")
            return None, None


class VLLMThread(QThread):
    signal = pyqtSignal(str, object, bool, bool) # string 
    def __init__(self, vlm_client):
        super().__init__()

        self.client = vlm_client
        self.client.warmup(prompt=instruc["default"], count=1)
        self.client.get_vlm_response(prompt=instruc["default"])
        self.send_flag = False
        # what's modified: warning flag
        self.warning_flag = False

        self.patrol_flag = False 
        self.usertracking_flag = False

    def run(self):
        while True:
            # print("vlm thread is spinning!")
            if self.send_flag:
                print("VLLMThread: send_flag is True, getting response...")
                # answer, image = self.client.get_vlm_response(prompt = instruc["person"])
                answer, image = self.client.get_vlm_response(use_audio=False)
                # downsample image 
                image = cv2.resize(image, (300, 250))
                self.send_flag = False
                # print("image shape:", image.shape)

                # user tracking & patrol check
                # VLM to Action mapping words!!!! <<<--- <<<--- <<<--- <<<---<<<---
                patrol_words = ["순찰", "시작"]
                usertracking_word = "따라"
                end_word = ["종료", "완료", "도착", "멈추", "멈춰", "멈추겠습니다"]

                if patrol_words[0] in answer and self.usertracking_flag == False:
                    if patrol_words[1] in answer:
                        # turn on patrol
                        self.patrol_flag = True
                if usertracking_word in answer and self.patrol_flag == False:
                    self.usertracking_flag = True 
                if any(word in answer for word in end_word):
                    self.patrol_flag = False 
                    self.usertracking_flag = False

                self.signal.emit(answer, image, self.patrol_flag, self.usertracking_flag)
                time.sleep(0.1)

            # what's modified: when warning flag, keep checking the scene
            elif self.warning_flag:
                print("VLLMThread: vlm is on user tracking, checking hazardous conditions...")
                # answer, image = self.client.get_vlm_response(prompt = instruc["person"])
                answer, image = self.client.get_vlm_response(prompt = instruc["user_track_warning"],use_audio=False)
                # downsample image 
                image = cv2.resize(image, (300, 250))

                end_word = ["종료", "완료", "도착", "멈추", "멈춰", "멈추겠습니다"]
                if any(word in answer for word in end_word):
                    self.patrol_flag = False 
                    self.usertracking_flag = False

                self.signal.emit(answer, image, self.patrol_flag, self.usertracking_flag)
                time.sleep(0.1)
            else:
                pass

def main():
    app = QApplication(sys.argv)
    vllm_client = VLLMClient(
        api_url = "http://localhost:8000",
        stt_client = STTClient(),
        tts_client = TTSClient(),
        zed_client=ZedClient()
    )
    vlm_thread = VLLMThread(vllm_client)
    qt_widget = DemoQtWidget(
        vlm_thread=vlm_thread,
        patrol_thread=None,
        usertracking_thread=None
    )
    qt_widget.show()
    app.exec_()

if __name__ == "__main__":
    main()