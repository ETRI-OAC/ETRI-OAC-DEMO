# ETRI-OpenPathRobotics-KoreaUniv Demo

4족 보행 로봇에 카메라, AI, 음성, 내비게이션을 결합한 데모 시스템입니다.

![system_overview](./docs/system_overview.png)

---

## 이 시스템이 하는 일

1. **OAK-D Pro W 카메라**로 사람을 인식하고 추적합니다
2. **Hailo-10 AI 가속기**로 사람의 자세(포즈)를 실시간 분석합니다
3. **Pan-Tilt 서보**로 카메라가 사람의 얼굴을 자동으로 따라갑니다
4. **얼굴 인식**으로 등록된 사람을 식별합니다
5. **VLM(비전 언어 모델)**로 카메라에 보이는 장면을 설명합니다
6. **음성 합성/인식(TTS/STT)**으로 한국어 대화를 합니다
7. **Nav2 내비게이션**으로 로봇이 자율 주행합니다

---

## 대상 하드웨어

**AMD Ryzen AI 350** 기반 시스템 (Ubuntu 24.04)

```
┌─ Ryzen AI 350 ──────────────────────────────┐
│  CPU: AMD Zen 5 (메인 처리)                   │
│  NPU: XDNA2 내장 (VLM 추론)                  │
│                                              │
│  M.2 슬롯 #2: Hailo-10 (카메라 포즈 분석)      │
│                                              │
│  USB3: OAK-D Pro W 카메라                     │
│  USB:  RPLidar + Dynamixel 서보              │
└──────────────────────────────────────────────┘
```

| 구성 요소 | 모델 | 역할 |
|----------|------|------|
| **CPU/NPU** | AMD Ryzen AI 350 | 메인 처리 + VLM 추론 (내장 NPU) |
| **AI 가속기** | Hailo-10 ×1~2 (M.2) | 아래 자동 감지 표 참고 |
| **카메라** | OAK-D Pro W (USB3) | 광각 스테레오 영상 + 깊이 |
| **LiDAR** | RPLidar (USB) | 장애물 감지, 내비게이션 |
| **서보** | Dynamixel ×2 (USB) | Pan-Tilt 카메라 제어 |
| **로봇** | CANINE 4족 보행 로봇 | 이동 플랫폼 |
| **OS** | Ubuntu 24.04 | — |

### Hailo-10 자동 할당

서버 시작 시 Hailo 장치 수를 자동 감지하여 할당합니다. 설정 불필요.

| Hailo 장치 수 | device[0] | device[1] |
|-------------|-----------|-----------|
| **1개** | Pose(OAK) + Face(공유) | — (STT는 CPU) |
| **2개** | Pose(OAK) + Face(공유) | STT(Whisper) |

> **NVIDIA GPU/CUDA 불필요** — 모든 AI 추론은 Hailo-10, Ryzen AI NPU, 또는 CPU에서 수행됩니다.

---

## 1단계: 소프트웨어 설치

### 1-1. Docker 설치

```bash
# Docker가 없다면 설치
curl -fsSL https://get.docker.com | sh

# sudo 없이 Docker 실행 (재부팅 필요)
sudo usermod -aG docker $USER
sudo reboot

# 재부팅 후 확인
docker run hello-world
```

### 1-2. Python 가상환경 만들기 (Ubuntu 24.04 필수)

Ubuntu 24.04는 시스템 Python에 `pip install`을 직접 실행하면 에러가 납니다.
가상환경을 만들어서 사용합니다. **처음 한 번만 만들면 됩니다.**

```bash
# 가상환경 생성
python3 -m venv ~/opr-venv

# 활성화 (터미널을 열 때마다 실행)
source ~/opr-venv/bin/activate

# 활성화되면 프롬프트 앞에 (opr-venv)가 붙습니다
# 이후 pip install은 그냥 사용 가능
pip install <패키지명>
```

> **팁:** 매번 `source`를 치기 싫다면 `.bashrc`에 추가하세요:
> ```bash
> echo 'source ~/opr-venv/bin/activate' >> ~/.bashrc
> ```
>
> **참고:** Docker 컨테이너 내부에서는 가상환경이 필요 없습니다 (Dockerfile에서 자동 처리됨).

### 1-3. Git LFS 설치 및 파일 받기

이 프로젝트의 일부 파일(AI 모델 등)은 용량이 커서 Git LFS로 관리됩니다.

```bash
sudo apt install git-lfs
cd ~/Documents/OPR_ETRI_Demo   # 프로젝트 폴더로 이동
git lfs install
git lfs pull
```

### 1-4. OAK-D Pro W 카메라 설정

카메라를 **USB3 포트(파란색)**에 연결하세요. USB2(검은색)는 대역폭이 부족합니다.

```bash
# USB 권한 설정 (처음 한 번만)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# 카메라 인식 확인
lsusb | grep 03e7
# 출력 예: Bus 001 Device 005: ID 03e7:2485 Intel Movidius MyriadX
```

### 1-5. Hailo-10 설치 (M.2 슬롯 #2)

Hailo-10을 M.2 슬롯 #2에 장착한 후:

```bash
# HailoRT 설치 (https://hailo.ai/developer-zone/ 에서 .deb 다운로드)
sudo dpkg -i hailort_*.deb
pip install hailort

# 장치 인식 확인
hailortcli fw-control identify
# Device ID가 출력되어야 합니다 (예: 0000:02:00.0)
# 서버 실행 시 Hailo 장치는 자동으로 감지됩니다
```

### 1-6. Hailo 모델 (자동 다운로드)

HEF 모델은 **서버 첫 실행 시 자동으로 다운로드**됩니다. 수동 설치 불필요.

자동 다운로드를 위해 `hailo_model_zoo`만 설치해 두세요:

```bash
pip install hailo_model_zoo
```

> 자동 다운로드된 모델은 `hailo_models/` 폴더에 저장됩니다.
> 인터넷 없는 환경에서는 미리 다운로드 후 복사:
> ```bash
> hailo model-zoo download --model yolov8s_pose --hw-arch hailo10h
> hailo model-zoo download --model scrfd_2.5g --hw-arch hailo10h
> mkdir -p hailo_models/
> cp yolov8s_pose.hef scrfd_2.5g.hef hailo_models/
> ```

### 1-7. Ryzen AI SDK 설치 (VLM 사용 시)

VLM(비전 언어 모델)을 사용하려면 AMD NPU 드라이버가 필요합니다.

```bash
# AMD Ryzen AI SDK 설치
# https://www.amd.com/en/developer/resources/ryzen-ai-software.html 에서 다운로드

# NPU 드라이버 로드
sudo modprobe amdxdna

# NPU 장치 확인
ls /dev/accel/accel*
# 출력: /dev/accel/accel0

# Python 패키지 설치
pip install onnxruntime-vitisai transformers pillow huggingface_hub
```

### 1-8. VLM 모델 다운로드

```bash
# 가상환경이 활성화되어 있어야 합니다 (프롬프트에 (opr-venv) 표시 확인)
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu',
    local_dir='vlm/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu'
)
print('다운로드 완료!')
"
```

### 1-9. NoMachine 설치 (원격 접속 시)

로봇 PC에 원격으로 접속하려면:

1. 로봇 PC와 내 PC 모두 [NoMachine](https://www.nomachine.com/) 설치
2. 같은 네트워크에서 NoMachine으로 접속
3. 접속 설정에서 **마이크/오디오 관련 설정 전부 끄기**

> **주의:** 로봇 PC에 모니터가 물리적으로 연결되어 있어야 합니다 (가상 모니터도 가능).

---

## 2단계: Docker 이미지 빌드

4개의 컨테이너를 순서대로 빌드합니다. **처음 한 번만 하면 됩니다.**

### 2-1. OAK-ROS2 컨테이너 (카메라 + 로봇 제어)

```bash
# HailoRT .deb 파일을 빌드 폴더에 복사 (선택 — 없어도 빌드 가능)
cp hailort_*.deb zed-ros2-workspace/docker/

cd zed-ros2-workspace/docker
./build.sh
# 약 10~20분 소요
cd ../..
```

### 2-2. VLM 컨테이너 (비전 언어 모델)

```bash
cd vlm/docker
./compose_up.sh
# 빌드가 끝나면 Ctrl+C로 종료
cd ../..
```

### 2-3. TTS-STT 컨테이너 (음성 합성/인식)

```bash
cd tts-stt/docker
./compose_up.sh
# 빌드가 끝나면 Ctrl+C로 종료
cd ../..
```

### 2-4. Face Recognition 컨테이너 (얼굴 인식)

```bash
# HailoRT .deb를 빌드 폴더에 복사 (Hailo 얼굴 검출 사용 시)
cp hailort_*.deb face-recognition/docker/

cd face-recognition/docker
./compose_up.sh
# 빌드가 끝나면 Ctrl+C로 종료
cd ../..
```

### 빌드 완료 후 재부팅 권장

```bash
sudo reboot
```

---

## 3단계: 서버 실행

### 방법 A: 한 번에 모두 실행 (권장)

```bash
./run_all_servers.sh
```

8개의 서버가 tmux 분할 화면에서 동시에 시작됩니다:

| 패널 | 서버 | 포트 |
|------|------|------|
| 0 | VLM (Gemma-3-4b-it-mm) | 8000 |
| 1 | STT (Whisper 음성인식) | 8001 |
| 2 | TTS (한국어 음성합성) | 8002 |
| 3 | Face Recognition (얼굴인식) | 7999 |
| 4 | CANINE Middleware (로봇 제어) | — |
| 5 | LiDAR (장애물 감지) | — |
| 6 | Pan-Tilt (카메라 서보) | — |
| 7 | OAK-D Camera (영상 + 포즈) | — |

> **tmux 사용법:** `Ctrl+B` → 방향키로 패널 이동, `Ctrl+B` → `D`로 빠져나오기

### 방법 B: 하나씩 실행 (문제 해결 시)

각 서버를 별도 터미널에서 실행할 수 있습니다:

```bash
# 터미널 1: 카메라 서버
cd zed-ros2-workspace
./run_oak_server.sh

# 터미널 2: VLM
cd vlm
./run_vlm_server.sh

# 터미널 3: STT
cd tts-stt
./run_stt_server.sh

# 터미널 4: TTS
cd tts-stt
./run_tts_server.sh

# 터미널 5: 얼굴 인식
cd face-recognition
./run_face_recognition_server.sh
```

---

## 4단계: 서버 작동 확인

각 서버가 정상인지 터미널을 열어 확인합니다:

```bash
# 카메라 확인
cd zed-ros2-workspace/docker && ./exec.sh
python3 -c "
import sys; sys.path.insert(0, '/root/workspace/zed-ros2-workspace/clients')
from zed_client import ZedClient
c = ZedClient()
img = c.grab_image(timeout=2.0)
print('카메라 OK' if img is not None else '카메라 연결 실패')
c.close()
"
exit

# VLM 확인
curl http://localhost:8000/health

# STT 확인 (녹음 파일이 있다면)
# curl -X POST -F "audio=@test.wav" http://localhost:8001/transcribe

# TTS 확인
curl -X POST http://localhost:8002/speak -H "Content-Type: application/json" -d '{"text":"안녕하세요"}'

# 얼굴 인식 확인
curl http://localhost:7999/health
```

---

## 5단계: 데모 실행

### 공통 준비 (모든 데모에 필요)

1. [3단계](#3단계-서버-실행)에서 서버가 모두 켜져 있어야 합니다
2. **Middleware GUI**에서 로봇을 **Walk** 모드로 변경합니다
3. Twist republisher를 실행합니다:
   ```bash
   cd zed-ros2-workspace/docker && ./exec.sh
   cd /root/workspace/zed-ros2-workspace/SLAM_Nav
   python repub_twist2canine.py
   ```

### 실외 데모: 사람 추적 (간단, 맵 불필요)

로봇이 카메라 앞의 사람을 따라다닙니다.

```bash
# 터미널 A: Nav2 실행
cd zed-ros2-workspace
./run_nav2_outdoor.sh

# 터미널 B: 데모 GUI 실행
cd zed-ros2-workspace/docker && ./exec.sh
cd /root/workspace/zed-ros2-workspace/test_scripts
python _22_usertracking_gui.py
```

### 실내 데모: 순찰 + 얼굴 인식 (맵 필요)

로봇이 정해진 경로를 순찰하면서 사람을 만나면 인식합니다.

> **사전 준비:**
> - 실내 맵이 필요합니다. 맵 만드는 방법은 [docs/slam-map.md](docs/slam-map.md) 참고
> - 얼굴 인식에는 사전 등록이 필요합니다: [docs/face-recognition-container.md](docs/face-recognition-container.md) 참고

```bash
# 터미널 A: Nav2 실행 (실내 맵 사용)
cd zed-ros2-workspace
./run_nav2_indoor.sh

# 터미널 B: 키보드로 로봇 위치 초기화
cd zed-ros2-workspace/docker && ./exec.sh
cd /root/workspace/zed-ros2-workspace/SLAM_Nav
python keyboard_teleop.py
# RViz에서 로봇 위치가 맞으면 Ctrl+C

# 터미널 C: 데모 GUI 실행
cd zed-ros2-workspace/docker && ./exec.sh
cd /root/workspace/zed-ros2-workspace/test_scripts
python _21_patrol_gui.py
```

### VLM 데모: 장면 설명

카메라에 보이는 것을 AI가 설명합니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd /root/workspace/zed-ros2-workspace/test_scripts
python _20_vlm_gui.py
```

---

## 종료 방법

```bash
# 모든 컨테이너 한 번에 종료
./kill_docker.sh

# ROS 2 노드만 종료
./kill_ros2_node.sh
```

---

## 문제 해결

### 카메라가 안 된다

| 증상 | 해결 |
|------|------|
| `No DepthAI device found` | USB3 포트(파란색)에 연결했는지 확인. `lsusb \| grep 03e7`으로 인식 확인 |
| 화면이 까맣다 | USB 케이블 교체. 전원 부족일 수 있음 |
| FPS가 20 이하 | USB2에 꽂혀 있음 → USB3로 변경 |

### Hailo-10이 안 된다

| 증상 | 해결 |
|------|------|
| `hailo_platform import error` | 가상환경 활성화 후 `pip install hailort` 확인. HailoRT .deb 설치 확인 |
| `hailortcli`에서 장치 안 보임 | `lspci \| grep Hailo`로 PCIe 인식 확인. M.2 슬롯 #2 재장착 |
| HEF 로드 실패 | `--hw-arch hailo10h`로 모델 재다운로드 |

### VLM이 안 된다

| 증상 | 해결 |
|------|------|
| 모델 다운로드 실패 | 인터넷 연결 확인. HuggingFace 계정 로그인 필요할 수 있음 |
| `VitisAI EP not available` | AMD Ryzen AI SDK 설치 확인. `sudo modprobe amdxdna` 실행 |
| 응답이 매우 느림 | NPU 미사용 중 (CPU fallback). Ryzen AI SDK 설치 확인 |

### 카메라 shared memory 끊김

Main script 종료 후 카메라 서버를 재시작해야 합니다:

```bash
cd zed-ros2-workspace
./run_oak_server.sh
```

### LiDAR / Pan-Tilt이 안 된다

USB를 뽑았다가 다시 꽂은 후:

```bash
cd zed-ros2-workspace && ./run_lidar.sh     # LiDAR 재시작
cd zed-ros2-workspace && ./run_pantilt.sh   # Pan-Tilt 재시작
```

### 컨테이너에 직접 들어가기

문제를 직접 확인하고 싶을 때:

```bash
# OAK-ROS2 컨테이너
cd zed-ros2-workspace/docker && ./exec.sh

# VLM 컨테이너
cd vlm/docker && ./exec.sh

# TTS-STT 컨테이너
cd tts-stt/docker && ./exec.sh

# Face Recognition 컨테이너
cd face-recognition/docker && ./exec.sh
```

---

## 시스템 구조 요약

```
┌─ AMD Ryzen AI 350 + Ubuntu 24.04 ─────────────────────────────┐
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐│
│  │  OAK-ROS2    │  │   TTS-STT    │  │   Face Recognition    ││
│  │  Container   │  │  Container   │  │     Container         ││
│  │              │  │              │  │                       ││
│  │ OAK-D Camera │  │ TTS (8002)   │  │ InsightFace (7999)    ││
│  │ Hailo[0]     │  │ STT (8001)   │  │ Hailo[0](검출공유)    ││
│  │ (Pose+Face)  │  │ Hailo[1]자동 │  │ +CPU(임베딩)          ││
│  │ Nav2         │  │              │  │                       ││
│  │ Middleware   │  └──────────────┘  └───────────────────────┘│
│  │ LiDAR       │                                              │
│  │ Pan-Tilt    │  ┌──────────────┐                            │
│  └──────────────┘  │     VLM      │                           │
│                    │  Container   │                           │
│                    │ Gemma-3-4b   │                           │
│                    │ Ryzen AI NPU │                           │
│                    │ (8000)       │                           │
│                    └──────────────┘                           │
└────────────────────────────────────────────────────────────────┘
```

---

## 각 컨테이너 상세 문서

| 컨테이너 | 문서 |
|----------|------|
| **OAK-ROS2** | [docs/zed-ros2-container.md](docs/zed-ros2-container.md) ※ 폴더명 `zed-ros2-workspace`는 레거시 |
| **VLM** | [docs/vlm-container.md](docs/vlm-container.md) |
| **TTS-STT** | [docs/tts-stt-container.md](docs/tts-stt-container.md) |
| **Face Recognition** | [docs/face-recognition-container.md](docs/face-recognition-container.md) |
