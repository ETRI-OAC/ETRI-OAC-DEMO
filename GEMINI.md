# Gemini Code-Context

## Project Overview

This project is a demonstration of a sophisticated robotics system integrated into a 4-legged robot. It combines computer vision, artificial intelligence, and voice interaction to perform a variety of tasks, including person tracking, face recognition, scene understanding, and autonomous navigation. The system is built on a foundation of ROS2 and Docker, with various AI models running on specialized hardware like the Hailo-10 AI accelerator and the AMD Ryzen AI NPU.

### Key Technologies

*   **Robotics:** ROS2, CANINE 4-legged robot
*   **AI Hardware:** Hailo-10, AMD Ryzen AI NPU
*   **Vision:** OAK-D Pro W Camera, RPLidar
*   **AI Models:**
    *   YOLOv8s-pose for pose estimation
    *   SCRFD for face detection
    *   InsightFace for face embedding
    *   Gemma-3-4b-it-mm for vision-language tasks
    *   Whisper for speech-to-text
    *   Sherpa-ONNX VITS for text-to-speech
*   **Containerization:** Docker

### Architecture

The system is architected as a set of microservices running in Docker containers:

*   **OAK-ROS2 Container:** Manages the OAK-D camera, robot control (via CANINE middleware), LiDAR, Pan-Tilt servos, and Nav2 for navigation.
*   **VLM Container:** Runs the Gemma-3-4b-it-mm vision-language model on the Ryzen AI NPU for scene understanding.
*   **TTS-STT Container:** Handles Korean speech-to-text (Whisper) and text-to-speech (Sherpa-ONNX).
*   **Face Recognition Container:** Performs face detection and recognition using InsightFace.

## Building and Running

### Initial Setup

Before running the project, you need to install Docker, Python, Git LFS, and set up the necessary hardware (OAK-D camera, Hailo-10). The `README.md` provides detailed instructions for this one-time setup.

### Building the Docker Images

Build the four Docker containers. This only needs to be done once.

```bash
# OAK-ROS2 Container
cd zed-ros2-workspace/docker
./build.sh
cd ../..

# VLM Container
cd vlm/docker
./compose_up.sh
# Press Ctrl+C to stop after the build is complete
cd ../..

# TTS-STT Container
cd tts-stt/docker
./compose_up.sh
# Press Ctrl+C to stop after the build is complete
cd ../..

# Face Recognition Container
cd face-recognition/docker
./compose_up.sh
# Press Ctrl+C to stop after the build is complete
cd ../..
```

### Running the Servers

You can run all the servers at once using a script:

```bash
./run_all_servers.sh
```

This will start all the necessary services in a `tmux` session.

### Running the Demos

There are several demos available, each with its own GUI. The servers must be running before starting a demo.

*   **Person Tracking (Outdoor):**
    ```bash
    # Terminal A: Start Nav2
    cd zed-ros2-workspace
    ./run_nav2_outdoor.sh

    # Terminal B: Start the demo GUI
    cd zed-ros2-workspace/docker && ./exec.sh
    cd /root/workspace/zed-ros2-workspace/test_scripts
    python _22_usertracking_gui.py
    ```

*   **Patrol + Face Recognition (Indoor):**
    ```bash
    # Terminal A: Start Nav2 with an indoor map
    cd zed-ros2-workspace
    ./run_nav2_indoor.sh

    # Terminal B: Initialize robot position
    cd zed-ros2-workspace/docker && ./exec.sh
    cd /root/workspace/zed-ros2-workspace/SLAM_Nav
    python keyboard_teleop.py

    # Terminal C: Start the demo GUI
    cd zed-ros2-workspace/docker && ./exec.sh
    cd /root/workspace/zed-ros2-workspace/test_scripts
    python _21_patrol_gui.py
    ```

*   **VLM Scene Description:**
    ```bash
    cd zed-ros2-workspace/docker && ./exec.sh
    cd /root/workspace/zed-ros2-workspace/test_scripts
    python _20_vlm_gui.py
    ```

## Development Conventions

*   **Containerization:** The entire system is containerized with Docker, promoting modularity and reproducibility. Each major component runs in its own container.
*   **Microservices:** The architecture follows a microservices pattern, with services communicating over the network (e.g., REST APIs).
*   **ROS2:** ROS2 is used for communication between the different hardware components and software modules, particularly within the `OAK-ROS2` container.
*   **AI Model Management:** AI models are either downloaded automatically on the first run or managed with Git LFS.
*   **Hardware Acceleration:** The system is designed to take advantage of specialized hardware for AI inference, such as the Hailo-10 and Ryzen AI NPU.
