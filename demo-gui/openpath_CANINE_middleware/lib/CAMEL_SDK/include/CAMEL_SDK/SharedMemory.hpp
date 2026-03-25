//
// Created by ys on 24. 2. 16.
//

#ifndef RBCANINE_SHAREDMEMORY_HPP
#define RBCANINE_SHAREDMEMORY_HPP

#include <Eigen/Dense>
#include <Eigen/Core>
#include "ENumClasses.hpp"

#define CAMEL_PI          3.141592
#define R2D         57.2957802
#define D2R         0.0174533

#define MAX_PODO_NUM 10

#define RT_MS       2
#define dT 0.002
#define MAX_JOINT 12
#define MAX_LEG 4

#define CMD_dT              0.002
#define HIGH_CONTROL_dT     0.01
#define LOW_CONTROL_dT      0.002
#define SHORT_PREDICTION_dT      0.02
#define LONG_PREDICTION_dT      0.1
#define LOW_CONTROL_FREQ    500
#define VISUAL_dT           0.002
#define ESTIMATOR_dT        0.002
#define MAX_COMMAND_DATA        40
#define MPC_HORIZON         8

/// --------------------------- Struct Information ---------------

typedef struct _GAMEPAD_
{
    float L_UD = 0.0f, L_RL = 0.0f, R_UD = 0.0f, R_RL = 0.0f;
    float LT = 0.0f, RT = 0.0f;
    bool BTN[16] = {false,};
    bool status = false;
} GAMEPAD, *pGAMEPAD;

typedef struct __LAN_STRUCT_JOYSTICK__
{
    float axisLeftX = 0.0f;
    float axisLeftY = 0.0f;

    float axisRightX = 0.0f;
    float axisRightY = 0.0f;

    float triggerLeft = 0.0f;
    float triggerRight = 0.0f;

    unsigned char buttons[16] = {0,};
} LAN_JOYSTICK;

typedef struct __LAN_STRUCT_MIDDLEWARE__
{
    float linearVelocityX = 0.0f;
    float linearVelocityY = 0.0f;
    float angularVelocityZ = 0.0f;
} LAN_MIDDLEWARE;

typedef struct _COMMAND_STRUCT_
{
    int     COMMAND_TARGET = 0;
    int     USER_COMMAND = 0;
    char    USER_PARA_CHAR[MAX_COMMAND_DATA] = {0,};
    int	    USER_PARA_INT[MAX_COMMAND_DATA] = {0,};
    float   USER_PARA_FLOAT[MAX_COMMAND_DATA] = {0.0f,};
    double  USER_PARA_DOUBLE[MAX_COMMAND_DATA] = {0.0,};
} COMMAND_STRUCT, *pCOMMAND_STRUCT;

typedef struct _ROBOT_RAW_DATA_
{
    struct
    {
        double position[MAX_JOINT];
        double velocity[MAX_JOINT];
        double torque[MAX_JOINT];
        double temperature[MAX_JOINT];
        double voltage[MAX_JOINT];
        double Kp[MAX_JOINT];
        double Kd[MAX_JOINT];
        int error_code[MAX_JOINT];
        bool status[MAX_JOINT];
    } motor;

    struct
    {
        Eigen::Quaterniond quat;
        Eigen::Vector3d rpy;
        Eigen::Vector3d gyro;
        Eigen::Vector3d acc;
    } IMU;

    GAMEPAD gamepad;

    double battery_voltage;
    bool can_check;
    bool find_home;
    bool control_start;

} ROBOT_RAW_DATA;

typedef struct _MIDDLEWARE_DATA_
{
    int FSMState;
    double localTime;

    struct
    {
        Eigen::Vector3d baseVelocity;
        Eigen::Vector3d baseAngularVelocity;
    } body;

    struct
    {
        Eigen::Vector3d basePosition;
        Eigen::Vector3d baseVelocity;
        Eigen::Vector3d baseAngularVelocity;
        Eigen::Vector3d rpy; // body orientation[rpy]
        Eigen::Vector4d quat; // body orientation[quat]
    } global;


} MIDDLEWARE_DATA;

typedef struct _ROS2_DATA_
{
    bool isConnected = false;
    int command = 0;
    int prevCommand = 0;
    bool bNewCommand = false;
    float baseRefVelX;
    float baseRefVelY;
    float baseRefAngVelZ;
} ROS2_DATA;

// ===================================================
// LAN Structure
typedef struct _LAN_STRUCT_CAMEL2GUI_
{
    FSM fsm_state;
    int compliant_state;
    int gait_state;
    bool leg_contact[MAX_LEG];
    bool bGDMCommand;
    bool bConsoleCommand;
    bool bVisionAvailable;
    bool bTurboMode;
    bool bVisionMode;
    Eigen::Vector3d cmd_vel;
    Eigen::Vector3d actual_vel;

    bool isVisionUdpConnected;
    bool isROSConnected;

    double batteryVoltage;

    ROBOT_RAW_DATA rawData;
    double desiredTorque[MAX_JOINT];
    double desiredPosition[MAX_JOINT];

    MIDDLEWARE_DATA middlewareData;
} LAN_CAMEL2GUI, *pLAN_CAMEL2GUI;

#endif //RBCANINE_SHAREDMEMORY_HPP
