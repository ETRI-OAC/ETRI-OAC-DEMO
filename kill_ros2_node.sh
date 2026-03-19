#!/bin/bash
# Gracefully stop all ROS 2 nodes, then force-kill if still running.

echo "Stopping ROS 2 nodes..."

# Try graceful shutdown first (SIGTERM)
ros2_pids=$(pgrep -f "ros2|rplidar_node|pantiltNode|repub_twist|nav2|canine_middleware" 2>/dev/null)

if [ -z "$ros2_pids" ]; then
    echo "No ROS 2 processes found."
    exit 0
fi

echo "Sending SIGTERM to: $ros2_pids"
kill $ros2_pids 2>/dev/null

# Wait up to 5 seconds for graceful shutdown
for i in $(seq 1 5); do
    remaining=$(pgrep -f "ros2|rplidar_node|pantiltNode|repub_twist|nav2|canine_middleware" 2>/dev/null)
    if [ -z "$remaining" ]; then
        echo "All ROS 2 nodes stopped."
        exit 0
    fi
    sleep 1
done

# Force kill remaining
echo "Force killing remaining: $remaining"
kill -9 $remaining 2>/dev/null
echo "Done."
