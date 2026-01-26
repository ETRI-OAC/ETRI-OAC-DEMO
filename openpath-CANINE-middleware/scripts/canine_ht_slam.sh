#!/bin/bash

#############################################################
#  터미널 1 : LiDAR 실행 (RPLiDAR)
#############################################################
gnome-terminal --tab --title="RPLiDAR" -- bash -c "
echo '[Terminal1] Starting RPLiDAR...'
source /opt/ros/humble/setup.bash

cd ~/Library/install
source setup.bash
cd ~/Library

ros2 run rplidar_ros rplidar_node \
--ros-args \
-p serial_port:=/dev/ttyUSB1 \
-p serial_baudrate:=1000000 \
-p scan_frequency:=20.0

exec bash
"

sleep 1

#############################################################
#  터미널 2 : Middleware 실행
#############################################################
gnome-terminal --tab --title="Middleware" -- bash -c "
echo '[Terminal2] Starting Middleware...'
source /opt/ros/humble/setup.bash

cd ~/OPR/openpath-CANINE-middleware/scripts
./build_middleware.sh
./run_middleware.sh

exec bash
"

sleep 1

#############################################################
#  터미널 3 : SLAM Toolbox 실행
#############################################################
gnome-terminal --tab --title="SLAM Toolbox" -- bash -c "
echo '[Terminal3] Starting SLAM Toolbox...'
source /opt/ros/humble/setup.bash

cd /opt/ros/humble/share/

ros2 launch slam_toolbox online_async_launch.py \
use_sim_time:=false \
params_file:=/home/rilab-orin/online_async.yaml

exec bash
"

sleep 1

#############################################################
#  터미널 4 : RViz 실행
#############################################################
gnome-terminal --tab --title="RViz" -- bash -c "
echo '[Terminal4] Starting RViz...'
source /opt/ros/humble/setup.bash

rviz2

exec bash
"

echo "===================================================="
echo "  All processes launched!"
echo "  Terminal1: RPLiDAR"
echo "  Terminal2: Middleware"
echo "  Terminal3: SLAM Toolbox"
echo "  Terminal4: RViz"
echo "===================================================="

