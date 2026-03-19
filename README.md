# ETRI-OpenPathRobotics-KoreaUniv Demo

## System Overview

![system_overview](./docs/system_overview.png)

각 컨테이너별 구동 서버와 구조는 아래 문서를 참고하세요.

| 컨테이너 | 문서 |
|----------|------|
| **OAK-ROS2** | [docs/zed-ros2-container.md](docs/zed-ros2-container.md) — OAK-D Camera, Hailo-10 Pose, Middleware, Lidar, Pan-Tilt |
| **VLM** | [docs/vlm-container.md](docs/vlm-container.md) — vLLM 기반 Vision-Language 서버 |
| **TTS-STT** | [docs/tts-stt-container.md](docs/tts-stt-container.md) — TTS / STT REST API |
| **Face Recognition** | [docs/face-recognition-container.md](docs/face-recognition-container.md) — 얼굴 인식 REST API |

---

> **빠른 시작:** 이미 세팅이 되어 있는 경우 [데모 실행](#데모-실행)부터 보시면 됩니다.
> **구동 전 필독:** [Tips and Issues](#tips-and-issues)

---

## 목차 (Table of Contents)

- [Preliminaries](#preliminaries)
- [Installation (컨테이너 빌드)](#installation-컨테이너-빌드)
- [맵 빌딩 (실내 데모용)](#맵-빌딩-실내-데모용)
- [데모 실행](#데모-실행)
- [Tips and Issues](#tips-and-issues)

---

## Preliminaries

### 구동 환경

| 항목   | 버전 / 장치  |
|--------|-------------|
| Ubuntu | 24.04       |
| ROS 2  | Jazzy Jalisco |
| 카메라 | OAK-D Pro (DepthAI) |
| AI 가속기 | Hailo-10 (YOLOv8s-pose) |
| CUDA   | 12.6        |

### 1. Git LFS 파일 받아오기

**레포지토리 폴더 안에서 진행하세요.**

```bash
sudo apt install git-lfs
git lfs install
git lfs pull
```

### 2. OAK-D Pro USB 설정

OAK-D Pro를 **USB3 포트**에 연결하세요 (USB2는 대역폭 부족).

```bash
# USB 장치 인식 확인
lsusb | grep 03e7

# udev 권한 설정 (처음 한 번만)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Hailo-10 설치

1. [Hailo Developer Zone](https://hailo.ai/developer-zone/)에서 HailoRT `.deb` 패키지 다운로드
2. 설치:
   ```bash
   sudo dpkg -i hailort_*.deb
   pip install hailort
   ```
3. 장치 확인:
   ```bash
   hailortcli fw-control identify
   ```

### 4. YOLOv8s-pose HEF 모델 다운로드

```bash
pip install hailo_model_zoo
hailo model-zoo download --model yolov8s_pose --hw-arch hailo10h
# 결과 파일을 프로젝트에 복사
cp yolov8s_pose.hef zed-ros2-workspace/oak_wrapper/models/
```

### 5. Sudo 없이 Docker 실행

```bash
sudo usermod -aG docker $USER
newgrp docker
sudo reboot
```

### 6. NoMachine 설치 및 설정

1. 로봇 PC 및 원격 데스크탑 모두 [NoMachine](https://www.nomachine.com/) 설치
2. 같은 네트워크에서 NoMachine으로 로봇에 원격 접속
3. 접속 설정에서 **마이크·오디오 관련 설정 전부 끄기** (켜져 있으면 원격 데스크탑이 입출력을 가져감)

> **주의:** NoMachine 구동 시 가상/실제 디스플레이가 PC에 **물리적으로 연결**되어 있어야 합니다.

---

## Installation (컨테이너 빌드)

아래 순서대로 각 컨테이너를 빌드하세요.
**모든 빌드 후 안정화를 위해 재시동을 권장합니다.**

| 순서 | 컨테이너 | 명령 |
|------|----------|------|
| 1 | **OAK-ROS2** | `zed-ros2-workspace/docker` → `./build.sh` |
| 2 | **VLM** | `vlm` → `./run_vlm_server.sh` (첫 실행 후 Ctrl+C로 종료) |
| 3 | **TTS-STT** | `tts-stt/docker` → `./compose_up.sh` (빌드 후 Ctrl+C) |
| 4 | **Face Recognition** | `face-recognition/docker` → `./compose_up.sh` (빌드 후 Ctrl+C) |

### OAK-ROS2 Container

```bash
# HailoRT .deb를 docker 빌드 컨텍스트에 복사 (선택 — 없어도 빌드 가능)
cp hailort_*.deb zed-ros2-workspace/docker/

cd zed-ros2-workspace/docker
./build.sh
```

### VLM Container

```bash
cd vlm
./run_vlm_server.sh
# 첫 서버 실행 후 Ctrl+C로 종료
```

### TTS-STT Container

```bash
cd tts-stt/docker
./compose_up.sh   # 이미지 빌드 대기 후 Ctrl+C
```

### Face Recognition Container

```bash
cd face-recognition/docker
./compose_up.sh   # 이미지 빌드 대기 후 Ctrl+C
```

---

## 맵 빌딩 (실내 데모용)

실내 데모는 **사전에 만든 맵**이 필요합니다. 맵이 없으면 SLAM으로 맵을 만든 뒤 저장해야 합니다.
자세한 순서와 명령은 [SLAM 및 맵 저장](docs/slam-map.md)을 참고하세요. (요약 명령: `zed-ros2-workspace/SLAM_Nav/commands.txt`)

---

## 데모 실행

**[공통](#공통)** 실행 후 **[실내 데모](#실내-데모)** 또는 **[실외 데모](#실외-데모)** 중 하나를 실행하세요.

### 공통

1. NoMachine으로 로봇 PC에 접속

2. **Terminal 1 — 서버 기동**
   ```bash
   ./run_all_servers.sh   # tmux 기반 서버 세션
   ```
   > OAK-D 카메라 서버는 `--hef` 인자로 YOLOv8s-pose 모델 경로를 지정합니다.
   > 모델 없이 실행 시 카메라 영상만 제공됩니다 (바디 트래킹 없음).

3. **Middleware GUI**에서 로봇을 **Walk** 모드로 변경

4. **Terminal 2 — Canine ↔ Twist republisher**
   ```bash
   cd zed-ros2-workspace/docker && ./exec.sh
   cd zed-ros2-workspace/SLAM_Nav && python repub_twist2canine.py
   ```

5. **Terminal 3 — RViz**
   ```bash
   cd zed-ros2-workspace/docker && ./exec.sh
   ros2 run rviz2 rviz2 -d $(ros2 pkg prefix nav2_bringup)/share/nav2_bringup/rviz/nav2_default_view.rviz
   ```

---

### 실내 데모

> 실행 전 **RViz**와 **키보드 텔레옵**으로 **Localization 초기화**를 진행해야 합니다.
> 맵이 없으면 [SLAM 및 맵 저장](docs/slam-map.md)을 먼저 진행하세요.
> 얼굴 인식을 쓰려면 [Face Recognition — 얼굴 등록](docs/face-recognition-container.md#얼굴-등록-register)을 참고해 사전 등록을 진행하세요.

| 터미널 | 역할 | 명령 |
|--------|------|------|
| **Terminal 4** | Nav2 (Prebuilt Map) | `cd zed-ros2-workspace && ./run_nav2_indoor.sh` |
| **Terminal 5** | Keyboard Teleop | 아래 코드 블록 참고 (초기화 후 Ctrl+C) |
| **Terminal 6** | Main Script | `_21_patrol_gui.py` |

**Terminal 5 — Keyboard Teleop**
```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd zed-ros2-workspace/SLAM_Nav && python keyboard_teleop.py
# 초기 localization 후 Ctrl+C
```

**Terminal 6 — Main Script**
```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd zed-ros2-workspace/test_scripts
python _21_patrol_gui.py
```

---

### 실외 데모

> 맵 없이 진행하므로 **Localization 초기화는 생략** 가능합니다.

| 터미널 | 역할 | 명령 |
|--------|------|------|
| **Terminal 4** | Nav2 (No Map & User Tracking) | `cd zed-ros2-workspace && ./run_nav2_outdoor.sh` |
| **Terminal 5** | Main Script | `_22_usertracking_gui.py` |

**Terminal 5 — Main Script**
```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd zed-ros2-workspace/test_scripts
python _22_usertracking_gui.py
```

---

## Tips and Issues

### 카메라 shared memory 끊김

Main script가 종료될 때마다 카메라 서버의 shared memory 연결이 끊길 수 있습니다.
**Main script 실행 전** 카메라 서버를 재시작하세요.

```bash
cd zed-ros2-workspace
./run_zed_server.sh
```

### OAK-D Pro 연결 문제

| 증상 | 해결 |
|------|------|
| `No DepthAI device found` | USB3 포트 확인, `lsusb \| grep 03e7`, udev 규칙 설치 |
| 낮은 FPS (<20) | USB2 포트 사용 중 → USB3(파란색)으로 변경 |
| 프레임 깨짐 | USB 케이블 교체 (전원 공급 부족 가능) |

### Hailo-10 문제

| 증상 | 해결 |
|------|------|
| `hailo_platform import error` | `pip install hailort` 및 HailoRT `.deb` 설치 확인 |
| `hailortcli` 장치 미인식 | PCIe/M.2 연결 확인, `lspci \| grep Hailo` |
| HEF 로드 실패 | `--hw-arch hailo10h`로 재다운로드 |

### VLM 서버

- 기동까지 **최대 5분** 소요될 수 있습니다.
- 서버 기동 후 **첫 번째 query 응답**이 나올 때까지 **네트워크 연결**을 유지해야 합니다.

### 전체 컨테이너 초기화

오류 시 모든 컨테이너를 한 번에 종료하려면:

```bash
./kill_docker.sh
```

### Lidar / Pan-Tilt 서버

함께 꺼졌을 경우: 해당 USB를 **탈부착**한 뒤 아래처럼 각각 재기동하세요.

```bash
cd zed-ros2-workspace && ./run_lidar.sh    # lidar server
cd zed-ros2-workspace && ./run_pantilt.sh  # pan-tilt server
```

### 컨테이너별 터미널 접속 (VLM 제외)

| 단계 | 명령 |
|------|------|
| Terminal 1 (컨테이너 실행) | `cd {each_directory}/docker && ./compose_up.sh` *(run_all_servers.sh 사용 시 생략 가능)* |
| Terminal 2 (쉘 접속) | `cd {each_directory}/docker && ./exec.sh` |

### Unit Test

각 서버에는 `*_client.py` 형태의 클라이언트 테스트 코드가 있습니다.
서버가 켜진 상태에서 해당 컨테이너에 접속한 뒤 `*_client.py`를 실행하면 됩니다.
