# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Robotics demo system for Ubuntu 24.04 (Desktop, x86_64) integrating OAK-D Pro stereo camera (DepthAI), ROS 2 Jazzy Jalisco navigation, vision-language model inference, Korean TTS/STT, face recognition, and Dynamixel pan-tilt servos on a quadruped robot (CANINE middleware). Documentation is primarily in Korean.

## Architecture

Four Docker containers communicate over host network:

| Container | Base Image | Purpose | Port |
|-----------|-----------|---------|------|
| **OAK-ROS2** | `ros:jazzy-ros-base-noble` | ROS 2, Nav2, DepthAI (OAK-D Pro), CANINE middleware, LiDAR, pan-tilt | ROS 2 topics |
| **VLM** | `vllm/vllm-openai:latest` | vLLM with Qwen3-VL-4B (AWQ 4-bit) | 8000 |
| **TTS-STT** | `nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04` | Sherpa-ONNX Korean TTS + Whisper STT | TTS: 8002, STT: 8001 |
| **Face Recognition** | `ultralytics/ultralytics:latest` | InsightFace (ArcFace) | 7999 |

### Shared Memory IPC (`/dev/shm`)

Camera frames and body tracking data are shared between `oak_server.py` (writer, OAK-D Pro via DepthAI) and `zed_client.py` (reader) via two named shared memory segments with lock-based synchronization:

- **`zed_image_shm`** — 28-byte header (lock, magic `0x5A494D47`, width, height, channels, dtype, frame_counter) + BGR pixel data
- **`zed_body_shm`** — 20-byte header (lock, magic `0x5A424F44`, frame_counter, num_bodies, body_format) + per-body data (id, confidence, position, velocity, 34 keypoints 2D/3D, bounding boxes; ~536 bytes each)

Lock protocol: writer sets lock=1 before writing, reader busy-waits with 1ms sleep. Pre-calculated offsets enable direct memcpy reads.

### REST API Endpoints

| Service | Endpoint | Method | Input | Output |
|---------|----------|--------|-------|--------|
| VLM | `/v1/chat/completions` | POST | OpenAI-compatible (base64 image + text) | Chat completion JSON |
| TTS | `/speak` | POST | `{text, speed}` | Synthesizes + plays on device speakers |
| TTS | `/speak_async` | POST | `{text, speed}` | Non-blocking variant |
| STT | `/transcribe` | POST | WAV/M4A audio file | `{text: "..."}` |
| Face | `/recognize` | POST | BGR image (JPEG) | `{name, similarity, success}` |
| Face | `/health` | GET | — | Health check |

### ROS 2 Topics

| Topic | Message Type | Purpose |
|-------|-------------|---------|
| `canine_states` | CANINEState | Quadruped FSM state, base position/velocity/orientation |
| `canine_command` | CANINECommand | Motion commands to quadruped (published @ 50Hz) |
| `cmd_vel` | geometry_msgs/Twist | Nav2 velocity output → converted by `repub_twist2canine.py` |
| `scan` | LaserScan | LiDAR data for Nav2/AMCL |
| `pantilt_state` | — | Pan-tilt servo position feedback |
| `pantilt_command` | — | Pan-tilt target position |

### CANINE Middleware (`openpath_CANINE_middleware/python_scripts/`)

Three-thread architecture in `main.py`:
1. **rosCommunicationThread** — ROS 2 node subscribing to `canine_states`, publishing `canine_command`
2. **pantiltMotorControlThread** — Dynamixel servo control on `/dev/ttyUSB0` @ 2Mbaud (yaw ID:101, pitch ID:102; limits: yaw ±45°, pitch -35°/+30°)
3. **SharedMemoryManager** — Thread-safe state holder for robot pose, velocity, pan-tilt position, FSM state

Command enums: `NO_INPUT, START, READY, STAND, WALK`
FSM states: `INITIAL, INITIALIZING, READY, HOME_UP, HOME_DOWN, EMERGENCY_STOP, STAND, WALK, RLWALK, STAIR, PRONKING, BOUNDING, PACING`

## Common Commands

### Build containers (first-time setup, run in order)
```bash
cd zed-ros2-workspace/docker && ./build.sh          # ZED-ROS2
cd vlm && ./run_vlm_server.sh                        # VLM (Ctrl+C after first run)
cd tts-stt/docker && ./compose_up.sh                 # TTS-STT (Ctrl+C after build)
cd face-recognition/docker && ./compose_up.sh        # Face Recognition (Ctrl+C after build)
```

### Launch all servers
```bash
./run_all_servers.sh    # tmux session with 8 services: VLM, STT, TTS, Face, Middleware, LiDAR, Pan-Tilt, ZED Server
```

### Enter a running container
```bash
cd {service}/docker && ./exec.sh    # Works for zed-ros2-workspace, tts-stt, face-recognition
```

### Test individual services (run inside respective container)
```bash
python vlm/test_client.py
python tts-stt/tts_client.py
python tts-stt/stt_client.py
python face-recognition/face_recognition_client.py
```

### Cleanup
```bash
./kill_docker.sh        # Stop all containers
./kill_ros2_node.sh     # Kill ROS 2 nodes
```

### Run demos (after `run_all_servers.sh` + middleware Walk mode + twist republisher)
```bash
# Indoor patrol (requires pre-built map + localization init)
cd zed-ros2-workspace && ./run_nav2_indoor.sh
cd zed-ros2-workspace/test_scripts && python _21_patrol_gui.py

# Outdoor user tracking (no map needed)
cd zed-ros2-workspace && ./run_nav2_outdoor.sh
cd zed-ros2-workspace/test_scripts && python _22_usertracking_gui.py
```

## Key Code Locations

- **Client libraries** (`zed-ros2-workspace/clients/`): Shared Python clients used by demo scripts to talk to each service — `zed_client.py` (shared memory), `vlm_client.py`, `tts_client.py`, `stt_client.py`, `face_recognition_client.py`
- **Demo scripts** (`zed-ros2-workspace/test_scripts/`): PyQt5 GUI applications (`_20_*` through `_22_*`, `23_*`) and incremental test scripts (`1_*` through `9_*`)
- **GUI framework** (`zed-ros2-workspace/gui/`): `gui.py` (PyQt5 layout), `gui_threads.py` (QThread workers for non-blocking service calls)
- **Nav2 config** (`zed-ros2-workspace/SLAM_Nav/`): `config/nav2_params.yaml` (AMCL omni-directional model), `config/following_params.yaml` + `config/bt_following.xml` (outdoor following behavior tree), `map/map_etri.yaml` (saved indoor map)
- **Twist-to-CANINE bridge** (`zed-ros2-workspace/SLAM_Nav/repub_twist2canine.py`): Converts Nav2 `cmd_vel` Twist messages to CANINECommand (linear vx/vy + angular ωz)
- **Camera server** (`zed-ros2-workspace/oak_wrapper/oak_server.py`): Opens OAK-D Pro camera via DepthAI, runs on-device MoveNet pose estimation, writes frames + body tracking to `/dev/shm`
- **Camera utilities** (`zed-ros2-workspace/oak_wrapper/`): `person_tracker.py` (IoU-based SORT tracker for persistent body IDs), `head_pose_estimator.py` (geometric head orientation + bbox from COCO keypoints)
- **PID utilities** (`zed-ros2-workspace/utils/pid.py`): PID controller used for real-time pan-tilt face tracking
- **Service servers**: `face-recognition/face_recognition_server.py`, `tts-stt/tts_server.py`, `tts-stt/stt_server.py`, `vlm/run_vlm_server.sh`
- **Docker configs**: Each service has a `docker/` subdirectory with Dockerfile, compose file, and shell scripts

## Demo Script Progression

Test scripts in `zed-ros2-workspace/test_scripts/` build incrementally:
- `1_middleware.sh` → CANINE middleware connection
- `3_*` → Pan-tilt servo test
- `4_*` → ZED camera capture
- `5_*` → Face detection + pan-tilt tracking
- `6_*` → 3D body skeleton overlay
- `7_*` → Face recognition integration
- `8_*` → Face identification + navigation
- `9_*` → Full person following
- `_20_vlm_gui.py` → VLM query GUI with optional STT/TTS
- `_21_patrol_gui.py` → Indoor patrol: Nav2 waypoints + face ID + PID pan-tilt + VLM scene understanding
- `_22_usertracking_gui.py` → Outdoor: real-time person following via dynamic goal updates + pan-tilt centering
- `23_gui_integrated.py` → Combined demo

## Development Notes

- Camera shared memory connection breaks when main scripts exit; restart camera server (`./zed-ros2-workspace/run_zed_server.sh`) before re-running demo scripts
- VLM server takes up to 5 minutes to start; first query requires network connectivity. VLM container is reused on restart (model cached inside container)
- LiDAR/pan-tilt recovery after disconnect: physically re-plug USB, then run `./zed-ros2-workspace/run_lidar.sh` or `./zed-ros2-workspace/run_pantilt.sh`
- Face recognition requires pre-registration via `face-recognition/register_face.py` (stores pickled embeddings in `face-recognition/database/`)
- All containers mount project root to `/root/workspace/` — code edits on host are live inside containers
- Nav2 uses omni-directional motion model (`nav2_amcl::OmniMotionModel`) since the quadruped can strafe
- Korean TTS model files are stored via Git LFS (`tts-stt/tts_model/`); run `git lfs pull` after clone
- SLAM map building procedure is documented in `docs/slam-map.md`
- Old Jetson/L4T Dockerfile kept as `Dockerfile.l4t-humble` for reference; active build uses `Dockerfile.ubuntu-jazzy`
- Old ZED server kept in `zed_wrapper/` for reference; active camera server is `oak_wrapper/oak_server.py`
- Body tracking uses YOLOv8s-pose (COCO-17) on Hailo-10 accelerator; OAK-D Pro provides camera frames only (no on-device NN); keypoint index 0 = NOSE (used for pan-tilt); head orientation estimated geometrically from eye/ear keypoints
