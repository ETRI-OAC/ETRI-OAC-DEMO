# Gemini Code-Context

## Project Overview

This project is a demonstration of a robotics system integrated into a 4-legged robot. It combines computer vision, artificial intelligence, and voice interaction to perform person tracking, face recognition, scene understanding, and autonomous navigation. The system is built on ROS 2 Jazzy and Docker, with AI models running on specialized hardware (Hailo-10 AI accelerator, AMD Ryzen AI NPU).

### Key Technologies

*   **Robotics:** ROS 2 Jazzy Jalisco, CANINE 4-legged robot
*   **AI Hardware:** Hailo-10 (M.2), AMD Ryzen AI 350 NPU
*   **Vision:** OAK-D Pro W Camera (DepthAI), RPLidar
*   **AI Models:**
    *   YOLOv8m-pose for pose estimation (Hailo-10)
    *   SCRFD-10g for face detection (Hailo-10)
    *   InsightFace ArcFace for face embedding (CPU)
    *   Gemma-3-4b-it-mm for vision-language tasks (NPU, currently disabled)
    *   Whisper for speech-to-text (CPU)
    *   Sherpa-ONNX VITS for text-to-speech (CPU)
*   **Containerization:** Docker (6 containers)

### Architecture

The system is architected as microservices running in Docker containers:

*   **OAK-Camera Container** (`oak-camera/`): OAK-D Pro W camera via DepthAI, writes frames + body tracking to `/dev/shm`.
*   **Demo GUI Container** (`demo-gui/`): PyQt5 GUI demos, CANINE middleware, Nav2 SLAM config, pan-tilt servo control.
*   **Hailo Inference Container** (`hailo-inference/`): Multi-context Hailo-10 inference server (pose + face detection), face recognition (ArcFace).
*   **Nav2 Container** (`nav2/`): Nav2, AMCL, RPLidar for autonomous navigation.
*   **VLM Container** (`vlm/`): Gemma-3-4b-it-mm on Ryzen AI NPU (currently disabled).
*   **TTS-STT Container** (`tts-stt/`): Korean TTS (Sherpa-ONNX) + STT (Whisper).

## Building and Running

### Initial Setup

Before running the project, install Docker, Python, Git LFS, and set up the necessary hardware (OAK-D camera, Hailo-10). The `README.md` provides detailed instructions.

### Building the Docker Images

Build all 6 containers at once:

```bash
./build_all_docker.sh
```

Or individually:

```bash
cd oak-camera/docker && ./build.sh && cd ../..
cd hailo-inference/docker && ./build.sh && cd ../..
cd nav2/docker && ./build.sh && cd ../..
cd demo-gui/docker && ./build.sh && cd ../..
cd tts-stt/docker && ./compose_up.sh && cd ../..   # Ctrl+C after build
cd vlm/docker && ./compose_up.sh && cd ../..       # Ctrl+C after build (optional)
```

### Running the Servers

Run all servers at once:

```bash
./run_all_servers.sh
```

This opens a gnome-terminal window with 8 tabs for all services.

### Running the Demos

Servers must be running before starting a demo.

*   **Face Recognition (standalone, no map needed):**
    ```bash
    ./face_demo.sh
    ```

*   **Patrol + Face Recognition (indoor, map needed):**
    ```bash
    # Prerequisite: run_all_servers.sh running, robot in Walk mode
    ./patrol.sh
    ```

*   **Person Tracking (outdoor, no map needed):**
    ```bash
    # Terminal A: Start Nav2
    cd oak-camera && ./run_nav2_outdoor.sh

    # Terminal B: Start the demo GUI
    cd demo-gui/docker && ./exec.sh
    cd /root/workspace/demo-gui
    python3 _22_usertracking_gui.py
    ```

*   **VLM Scene Description (currently disabled):**
    ```bash
    cd demo-gui/docker && ./exec.sh
    cd /root/workspace/demo-gui
    python3 _20_vlm_gui.py
    ```

## Development Conventions

*   **Containerization:** 6 Docker containers, each with `docker/` subdirectory containing Dockerfile, compose file, and shell scripts.
*   **Microservices:** Services communicate over host network via REST APIs (VLM:8000, STT:8001, TTS:8002, Hailo:8003, Face:7999) and ROS 2 topics.
*   **Shared Memory IPC:** Camera frames and body tracking data shared via `/dev/shm` (`zed_image_shm`, `zed_body_shm`).
*   **ROS 2 Jazzy:** Used for robot control (`canine_states`/`canine_command`), navigation (`cmd_vel`, `scan`), and pan-tilt servo control.
*   **AI Model Management:** Hailo HEF models auto-download on first run. Korean TTS model stored via Git LFS.
*   **Hardware Acceleration:** Hailo-10 for pose/face detection, Ryzen AI NPU for VLM, CPU for embedding/TTS/STT.
