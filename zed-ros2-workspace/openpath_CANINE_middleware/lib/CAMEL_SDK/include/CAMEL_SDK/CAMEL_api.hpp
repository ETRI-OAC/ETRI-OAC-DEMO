//
// Created by ys on 25. 7. 1.
//

#ifndef CAMEL_API_HPP
#define CAMEL_API_HPP

#include "ENumClasses.hpp"
#include "SharedMemory.hpp"
#include "Thread.h"
#include "Log.hpp"

#define HAETAE

#define CPU_NO_DAEMON           2
#define CPU_NO_UART             3
#define CPU_NO_SPI              4
#define CPU_NO_CONTROL          5
#define CPU_NO_CAMEL_CONTROL    6
#define CPU_NO_MPC              7
#define CPU_NO_GDQ_LOGGER       8

enum _CAMEL_COMMAND_TARGET_
{
    CAMEL_CTRL = 0,
    CAMEL_PLATFORM
};

enum _HARDWARE_COMMAND_SET
{
    CMD_PLATFORM_NO_ACT = 200,
    CMD_PLATFORM_MOTOR_INIT,
    CMD_PLATFORM_CAN_CHECK,
    CMD_PLATFORM_FIND_HOME,
    CMD_PLATFORM_CON_START,
    CMD_PLATFORM_LEG_STOP,
    CMD_PLATFORM_LEG_START,
    CMD_PLATFORM_PLATFORM_RESET,
    CMD_PLATFORM_AUTO_START
};

enum _CAMEL_COMMAND_SET_
{
    CMD_CTRL_NO_ACT = 100,
    CMD_CTRL_START,
    CMD_CTRL_E_STOP,
    CMD_CTRL_STAND,
    CMD_CTRL_WALK,
    CMD_CTRL_RLWALK,
    CMD_CTRL_BOUNDING,
    CMD_CTRL_PACING,
    CMD_CTRL_PRONKING,
    CMD_CTRL_STAIR,
    CMD_CTRL_READY,
    CMD_CTRL_TURBO_MODE,
    CMD_CTRL_VISION_MODE,
};

enum _CAMEL_ROS_COMMAND_SET_
{
    CMD_ROS_NO_ACT = 0,
    CMD_ROS_START,
    CMD_ROS_READY,
    CMD_ROS_STAND,
    CMD_ROS_WALK,
};

enum _GAIN_MODE_SET_
{
    GAIN_NORMAL,
    GAIN_EMERGENCY,
    GAIN_RECOVERY,
    GAIN_STAND,
    GAIN_WALK,
    GAIN_RLWALK
};

enum class FootState
{
    SWING,
    CONTACT,
    SLIP,
    COLLISION
};

#endif //CAMEL_API_HPP
