#ifndef SHAREDMEMORY_H
#define SHAREDMEMORY_H
#include "CAMEL_SDK/SharedMemory.hpp"

#define ManiControlAL 4

typedef struct _CAMEL_SHM_
{
    bool bIsConnect = false;

    LAN_CAMEL2GUI CAMEL_DATA_NEW;

    COMMAND_STRUCT  COMMAND;
    bool NEWCOMMAND;
    ROS2_DATA ros2Data;
}CAMEL_SHM, *pCAMEL_SHM;
extern pCAMEL_SHM sharedCamel;

#endif // SHAREDMEMORY_H
