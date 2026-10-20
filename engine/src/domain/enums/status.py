# -*- coding: utf-8 -*-
"""
    This is a Simple enum interface with the status affecting resources.
"""
from enum import Enum


class Status(Enum):
    """
        The status are:
            REG= Register, ACT= Active, LOK= Locked,
            Dis= Disable, OVR= Overdue, ERR= Error, COM=Completed
    """
    REG = 0
    ACT = 1
    LOK = 2
    DIS = 3
    OVR = 4
    ERR = 5
    COM = 6
