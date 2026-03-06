# ZED-ROS2 Container

ZED 카메라, LiDAR, Pan-Tilt, CANINE 미들웨어, ROS2/NAV2를 하나의 Docker 컨테이너에서 구동합니다.  
컨테이너 이름: `base-zed_ros2_env-1`.

---

## 구동 서버 목록

| 서버 | 실행 스크립트 | 설명 |
|------|----------------|------|
| **ZED Server** | `run_zed_server.sh` → `zed_wrapper/zed_server.py` | ZED 카메라 영상·바디 트래킹을 공유 메모리로 제공 |
| **CANINE Middleware** | `run_middleware.sh` → `1_middleware.sh` → `canine_middleware` | 로봇 제어 GUI 및 Walk 모드 등 |
| **Lidar** | `run_lidar.sh` → `2_publish_lidar.sh` | RPLidar ROS2 노드 (스캔 퍼블리시) |
| **Pan-Tilt** | `run_pantilt.sh` → `pantiltNode.py` | Dynamixel Pan-Tilt 제어 ROS2 노드 |

데모 시 **Nav2**(실내/실외)와 **Twist republisher**는 이 컨테이너 안에서 별도 터미널로 실행합니다.

---

## 구조

### 1. ZED Server (`zed_server.py`)

- **역할:** ZED 카메라를 열고, 좌측 BGR 영상과 바디 트래킹 결과를 **공유 메모리**에 씁니다.
- **클라이언트:** 다른 프로세스(호스트 또는 컨테이너)가 같은 공유 메모리 이름으로 접속해 프레임을 읽습니다. 소켓 복사 없이 저지연 접근이 가능합니다.

**공유 메모리 세그먼트:**

| 이름 | 용도 |
|------|------|
| `zed_image_shm` | 좌측 카메라 BGR 이미지 (헤더 + 픽셀 데이터) |
| `zed_body_shm` | 바디 트래킹 (프레임 카운터, 바디 수, BODY_34 키포인트 2D/3D 등) |

**헤더 구조 (요약):**

- **이미지:** lock, magic(`ZIMG`), width, height, channels, dtype, frame_counter
- **바디:** lock, magic(`ZBOD`), frame_counter, num_bodies, body_format, 그 다음 바디별 직렬화 데이터

**설정:** 해상도 HD1200, 30fps, Body Tracking 모델 `HUMAN_BODY_FAST`, 포맷 `BODY_34`.

---

### 2. CANINE Middleware

- **역할:** OpenPath CANINE 로봇과 통신하는 GUI 애플리케이션. Walk 모드 전환 등 제어를 담당합니다.
- **실행:** `test_scripts/1_middleware.sh` → `openpath_CANINE_middleware` 빌드 디렉터리에서 `./canine_middleware` 실행.
- 데모 실행 시 **Middleware GUI에서 로봇을 Walk 모드로 변경**해야 합니다.

---

### 3. Lidar Server (`2_publish_lidar.sh`)

- **역할:** RPLidar ROS2 노드 실행. `/dev/ttyUSB1`, 1000000 baud, 20Hz 스캔.
- **출력:** ROS2 토픽으로 라이다 스캔 데이터 퍼블리시 (Nav2 및 SLAM에서 사용).

---

### 4. Pan-Tilt Server (`run_pantilt.sh`)

- **역할:** Dynamixel 서보 기반 Pan-Tilt를 ROS2 노드로 제어. USB 시리얼로 연결.
- **입출력:** ROS2 토픽/메시지로 목표 각도 수신, TF 브로드캐스트 등.

---

## 클라이언트 연동

- **ZED:** `zed-ros2-workspace` 내 `ZedClient` (공유 메모리 이름 `zed_image_shm`, `zed_body_shm` 지정 가능)로 이미지·바디 데이터 읽기.
- **Nav2/Republisher:** 동일 ZED-ROS2 컨테이너에서 `repub_twist2canine.py`, `run_nav2_indoor.sh` / `run_nav2_outdoor.sh` 실행.

---

## 참고

- ZED Server는 **호스트와 컨테이너가 `/dev/shm`을 공유**해야 클라이언트가 같은 공유 메모리에 접근할 수 있습니다.
- Main 스크립트 종료 시 ZED 공유 메모리 연결이 끊길 수 있으므로, 재실행 전 `run_zed_server.sh`로 ZED Server를 다시 띄우는 것이 안전합니다.
