# -*- coding: utf-8 -*-
"""
    On this Enum interface we have all the response codes for our methods
"""

from enum import Enum


class ResponseCodes(Enum):
    """
        The current response codes are:
            AOK = Success
            CRD = Created
            UPD = Updated
            NPD = Bad request
            FOR = Forbidden
            ERR = System error
    """
    AOK = 200
    CRD = 201
    UPD = 202
    NOK = 400
    FOR = 403
    NOF = 404
    ERR = 500
