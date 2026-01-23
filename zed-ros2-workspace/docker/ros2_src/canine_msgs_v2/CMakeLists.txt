cmake_minimum_required(VERSION 3.21)
project(canine_msgs_v2)
set(CMAKE_CXX_STANDARD 17)

if (CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif ()
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
        "msg/CANINECommand.msg"
        "msg/CANINEState.msg"

        DEPENDENCIES builtin_interfaces nav_msgs geometry_msgs
)

ament_package()