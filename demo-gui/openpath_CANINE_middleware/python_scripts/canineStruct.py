from enum import Enum

class Command(Enum):
    NO_INPUT = 0
    START = 1
    READY = 2
    STAND = 3
    WALK = 4

class CanineFSM(Enum):
    INITIAL = 0
    INITIALIZING = 1
    READY = 2
    HOME_UP = 3
    HOME_DOWN = 4
    EMERGENCY_STOP = 5
    RESTART = 6
    STAND = 7
    WALK = 8
    RLWALK = 9
    STOP = 10
    STAIR = 11
    PRONKING = 12
    BOUNDING = 13
    PACING = 14