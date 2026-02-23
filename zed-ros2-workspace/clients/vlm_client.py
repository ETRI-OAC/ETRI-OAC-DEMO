#!/usr/bin/env python3
"""
vLLM 서버 테스트 클라이언트
이미지를 업로드하고 "차가 몇 대 있는지" 질문하여 응답을 받습니다.
"""
import os, sys
import cv2
import base64
import json
import time
import requests
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
# import this script's directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stt_client import STTClient
from tts_client import TTSClient

class VLLMClient:
    """
    vLLM 서버 클라이언트
    """
    
    def __init__(self, api_url: str = "http://localhost:8000", model: str = "cpatonn/Qwen3-VL-4B-Instruct-AWQ-4bit",
                 max_tokens: int = 512, temperature: float = 0.7, stt_client: STTClient = None, tts_client: TTSClient = None):
        """
        vLLM 클라이언트 초기화
        
        Args:
            api_url: vLLM API 서버 URL
            model: 사용할 모델 이름
            max_tokens: 최대 토큰 수
            temperature: 생성 온도
        """
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.stt_client = stt_client
        self.tts_client = tts_client

    @staticmethod
    def encode_image(image_path: str) -> str:
        """이미지를 base64로 인코딩"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    @staticmethod
    def encode_image_from_array(image: np.ndarray) -> str:
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise ValueError("Failed to encode image array")
        return base64.b64encode(encoded.tobytes()).decode('utf-8')

    def query(self, 
              image: np.ndarray = None, 
              image_path: str = None, 
              prompt: str = None, 
              measure_time: bool = False,
              use_stt_input: bool = False,
              use_tts_output: bool = False) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        vLLM 서버에 이미지와 프롬프트를 전송하여 응답을 받습니다.
        
        Args:
            image_path: 이미지 파일 경로
            prompt: 질문 프롬프트
            measure_time: 응답 시간을 측정할지 여부
        
        Returns:
            (API 응답 딕셔너리, 응답 시간(초) 또는 None) 튜플
        """
        if use_stt_input:
            if self.stt_client is None:
                raise ValueError("STT client is not initialized")
            response, _ = self.stt_client.transcribe_from_mic(duration_sec=5)
            prompt = response.get("text", "")

        # 이미지를 base64로 인코딩
        try:
            if image is not None:
                base64_image = self.encode_image_from_array(image)
            else:
                base64_image = self.encode_image(image_path)
        except Exception as e:
            print(f"[VLM] Failed to encode image: {e}")
            return None, None

        # OpenAI 호환 API 형식으로 요청 구성
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
        
        # API 요청 전송
        start_time = time.time() if measure_time else None
        response = requests.post(
            f"{self.api_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # 응답 확인
        response.raise_for_status()
        response_json = response.json()
        
        elapsed_time = (time.time() - start_time) if measure_time else None
        if use_tts_output:
            if self.tts_client is None:
                raise ValueError("TTS client is not initialized")
            self.tts_client.speak(response_json["choices"][0]["message"]["content"])
        return response_json, elapsed_time


def main():
    """메인 함수"""
    # 설정
    image_path = Path(__file__).parent / "sample_image.jpeg"
    prompt = "이 이미지에서 차가 몇 대 있는지 알려주세요."
    api_url = "http://localhost:8000"
    warmup_count = 10
    
    # 이미지 파일 존재 확인
    if not image_path.exists():
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {image_path}")
        return
    
    print("=" * 60)
    print("vLLM 서버 테스트 클라이언트")
    print("=" * 60)
    print(f"📷 이미지: {image_path}")
    print(f"❓ 질문: {prompt}")
    print(f"🌐 API URL: {api_url}")
    print(f"🔥 Warmup 횟수: {warmup_count}")
    print("-" * 60)
    
    # 클라이언트 초기화
    client = VLLMClient(api_url=api_url)
    
    try:
        # Warmup 단계
        print(f"🔥 Warmup 시작 ({warmup_count}회)...")
        warmup_start = time.time()
        for i in range(warmup_count):
            try:
                response, _ = client.query(str(image_path), prompt, measure_time=False)
                print(f"  [{i+1}/{warmup_count}] Warmup 완료", end='\r')
            except Exception as e:
                print(f"\n❌ Warmup {i+1}번째 실패: {e}")
                return
        warmup_total_time = time.time() - warmup_start
        print(f"\n✅ Warmup 완료! (총 {warmup_total_time:.2f}초)")
        print("-" * 60)
        
        # 실제 측정 단계
        print("📤 측정 요청 전송 중...")
        response, elapsed_time = client.query(str(image_path), prompt, measure_time=True)
        
        # 응답 파싱
        if "choices" in response and len(response["choices"]) > 0:
            answer = response["choices"][0]["message"]["content"]
            
            print("✅ 응답 수신 완료!")
            print("-" * 60)
            print(f"⏱️  응답 시간: {elapsed_time:.2f}초")
            print("-" * 60)
            print("💬 답변:")
            print(answer)
            print("-" * 60)
            
            # 전체 응답 정보 출력
            if "usage" in response:
                usage = response["usage"]
                print("📊 사용량 정보:")
                print(f"  - 입력 토큰: {usage.get('prompt_tokens', 'N/A')}")
                print(f"  - 출력 토큰: {usage.get('completion_tokens', 'N/A')}")
                print(f"  - 총 토큰: {usage.get('total_tokens', 'N/A')}")
                print("-" * 60)
        else:
            print("❌ 응답 형식이 예상과 다릅니다.")
            print(f"응답: {json.dumps(response, indent=2, ensure_ascii=False)}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: vLLM 서버에 연결할 수 없습니다.")
        print(f"   서버가 {api_url}에서 실행 중인지 확인하세요.")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 오류: {e}")
        if hasattr(e.response, 'text'):
            print(f"   응답 내용: {e.response.text}")
    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

