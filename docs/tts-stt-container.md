# TTS-STT Container

음성 합성(TTS)과 음성 인식(STT) 서버를 **한 개의 Docker 컨테이너**에서 구동합니다.  
컨테이너 이름: `base-tts-stt-1`.  
같은 컨테이너 안에서 **TTS 서버**와 **STT 서버**는 각각 별도 프로세스로 실행됩니다.

---

## 구동 서버 목록

| 서버 | 실행 스크립트 | 기본 포트 | 진입점 |
|------|----------------|-----------|--------|
| **STT Server** | `tts-stt/run_stt_server.sh` | **8001** | `stt_server.py` |
| **TTS Server** | `tts-stt/run_tts_server.sh` | **8002** | `tts_server.py` |

두 서버 모두 **Flask** 기반 REST API이며, `0.0.0.0`으로 리스닝해 다른 컨테이너/호스트에서 접근할 수 있습니다.

---

## STT Server (음성 인식)

- **역할:** 녹음된 음성 파일을 업로드받아 **Whisper**로 텍스트로 변환합니다.
- **모델:** Whisper (기본 `small`, 로드 후 메모리에 상주).

**엔드포인트:**

| Method | 경로 | 설명 |
|--------|------|------|
| `POST` | `/transcribe` | `multipart/form-data`, 필드 `audio`에 음성 파일. WAV, M4A, MP3, FLAC 등(ffmpeg 지원 형식). 응답: `{ "success", "text" }` |
| `GET`  | `/gui` | GUI용: 최근 인식된 텍스트 반환 `{ "output": "..." }` |

**실행 예:**

```bash
./tts-stt/run_stt_server.sh
# 컨테이너 내: python stt_server.py (--port 8001, --host 0.0.0.0)
```

---

## TTS Server (음성 합성)

- **역할:** 텍스트를 받아 **Sherpa-ONNX** 기반 한국어 TTS로 음성으로 합성하고, 재생 후 응답합니다.
- **모델:** `tts_model/sherpa-onnx-korean-tts/vits-mimic3-ko_KO-kss_low` (스크립트 기준 경로).

**엔드포인트:**

| Method | 경로 | 설명 |
|--------|------|------|
| `POST` | `/speak` | JSON `{ "text", "speed"?(optional) }`. 합성 후 재생까지 완료한 뒤 응답 |
| `POST` | `/speak_async` | 비동기 재생. 요청은 즉시 반환되고, 재생은 백그라운드에서 수행 |
| `GET`  | `/health` | 서버 상태 확인 |
| `GET`  | `/gui` | GUI용: 최근 출력 텍스트 등 `{ "output": "..." }` |

**재생:** PortAudio(sounddevice)로 기본 출력 디바이스에 재생. 샘플레이트는 22050Hz 등 모델 출력을 48000Hz(또는 디바이스 지원 레이트)로 리샘플링해 사용합니다.

**실행 예:**

```bash
./tts-stt/run_tts_server.sh
# 컨테이너 내: python tts_server.py (--port 8002, --host 0.0.0.0)
```

---

## 구조 요약

```
base-tts-stt-1 (컨테이너)
├── stt_server.py  (포트 8001)  ← Whisper 기반 STT REST API
└── tts_server.py  (포트 8002)  ← Sherpa-ONNX 기반 TTS REST API
```

데모 클라이언트(`tts_client.py`, `stt_client.py`)는 `localhost:8002`, `localhost:8001`로 각각 접속합니다.  
`run_all_servers.sh`에서는 STT·TTS가 각각 별도 tmux 패널에서 실행됩니다.
