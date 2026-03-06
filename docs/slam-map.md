# SLAM 및 맵 저장

실내 데모는 **사전에 만든 맵**이 필요합니다. 맵이 없거나 새로 만들 때는 아래 순서대로 터미널을 띄운 뒤 SLAM을 돌리고 맵을 저장합니다.

> 명령만 빠르게 쓰고 싶다면 `zed-ros2-workspace/SLAM_Nav/commands.txt`를 참고하세요.

---

## 터미널 구성 (1~4)

SLAM 전에 로봇을 구동할 수 있도록 서버, republisher, RViz, 텔레옵을 먼저 띄웁니다.  
**Middleware GUI**에서 로봇을 **Walk** 모드로 바꾼 뒤 진행하세요.

### Terminal 1 — 서버 기동

전체 서버(VLM, TTS, STT, Face Recognition, Middleware, Lidar, Pan-Tilt, ZED Server)를 한 번에 띄웁니다. SLAM에는 Lidar·ZED 등이 필요합니다.

```bash
# 레포 루트에서
./run_all_servers.sh
```

### Terminal 2 — Republisher (Twist → CANINE)

Nav2나 키보드 텔레옵에서 나오는 `cmd_vel`(Twist)를 CANINE 로봇이 받는 메시지로 변환해 보냅니다. 이 노드가 떠 있어야 로봇이 움직입니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd zed-ros2-workspace/SLAM_Nav && python repub_twist2canine.py
```

### Terminal 3 — RViz

맵·스캔·로봇 위치를 보려면 RViz를 띄웁니다. SLAM 중에도 맵이 쌓이는 것을 확인할 수 있습니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix nav2_bringup)/share/nav2_bringup/rviz/nav2_default_view.rviz
```

### Terminal 4 — Keyboard Teleop

키보드로 로봇을 움직여 SLAM이 환경을 스캔할 수 있게 합니다. 이 터미널에서 조작하는 동안 다른 터미널에서 SLAM을 실행합니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
cd zed-ros2-workspace/SLAM_Nav && python keyboard_teleop.py
```

---

## SLAM 실행

위 1~4번 터미널을 띄운 뒤, **컨테이너에 접속한 터미널 하나 더** 열어서 SLAM을 실행합니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
# 컨테이너 안에서
ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/root/workspace/zed-ros2-workspace/SLAM_Nav/config/online_async.yaml
```

Terminal 4(키보드 텔레옵)로 로봇을 움직이면서 환경을 스캔합니다. RViz에서 맵이 쌓이는 것을 확인할 수 있습니다.

---

## 맵 저장

SLAM이 켜진 상태에서 **또 다른 터미널**로 컨테이너에 접속한 뒤 맵을 저장합니다.

```bash
cd zed-ros2-workspace/docker && ./exec.sh
# 컨테이널 안에서
ros2 run nav2_map_server map_saver_cli -f ~/workspace/map
```

저장된 `map.pgm`, `map.yaml`을 실내 Nav2에서 쓰는 맵 경로(예: `zed-ros2-workspace/SLAM_Nav/map/`)에 맞춰 두거나, `run_nav2_indoor.sh`가 참조하는 맵 파일 경로를 이 맵으로 바꿔 사용하면 됩니다.

---

## 실내 데모에서 사용

`run_nav2_indoor.sh`는 기본적으로 `SLAM_Nav/map/map_etri.yaml`을 사용합니다. 새로 만든 맵을 쓰려면 해당 디렉터리에 `map.yaml` / `map.pgm`을 넣거나, 스크립트/설정에서 맵 경로를 수정하면 됩니다.

**주의**: yaml 파일 안의 pgm 형식의 map 의 경로가 적절하게 들어가 있는지 확인하세요.