from enum import Enum


class Status(Enum):
    REG = 0  # Register
    ACT = 1  # Active
    LOK = 2  # Locked
    DIS = 3  # Disable
    OVR = 4  # Overdue
    ERR = 5  # Error
    COM = 6  # Completed
