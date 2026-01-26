#ifndef INDEXNOTATION_H
#define INDEXNOTATION_H

#include <QPen>
#include <stdio.h>
#include <QDebug>

#include "Eigen/Dense"
#include "Eigen/Core"

#define MAX_MC      12
#define MAX_JOINT   12
#define MAX_LEG      4

#define MOVE_RELATIVE   1
#define MOVE_ABSOLUTE   0

#define CAMEL_PI			3.141592653589793
#define D2R			1.745329251994330e-2
#define R2D			5.729577951308232e1

#define ROBOT_ADDRESS "192.168.0.3"



// Utility ----------------------------
#define LOG_FAIL    "\033[1;31m"
#define LOG_GOOD    "\033[1;32m"
#define LOG_WARN    "\033[1;33m"
#define LOG_NORMAL  "\033[0m"

enum JointSequentialNumber
{
    J0 = 0,
    J1,
    J2,
    J3,
    J4,
    J5,
    J6,
    J7,
    J8,
    J9,
    J10,
    J11,
    NO_OF_JOINTSJ
};

const std::string JointNameList[NO_OF_JOINTSJ] = {
    "JNT0",
    "JNT1",
    "JNT2",
    "JNT3",
    "JNT4",
    "JNT5",
    "JNT6",
    "JNT7",
    "JNT8",
    "JNT9",
    "JNT10",
    "JNT11"
};

enum JointSequentialNumberBYNAME
{
    HRR, HRP, HRK,
    HLR, HLP, HLK,
    FRR, FRP, FRK,
    FLR, FLP, FLK,

    ///--- Mani Joint Name ---///
    M0Y, M1P, M2P,
    M3Y, M4P, M5Y,
    M6E,
    NO_OF_JOINTS
};

enum LegSequence
{
    HR, HL, // hind right-left
    FR, FL, // front right-left
    NO_OF_LEGS
};

enum TASK
{
    NO_TASK,
};

#endif // INDEXNOTATION_H
