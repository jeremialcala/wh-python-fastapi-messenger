"""
    This is a test Module for the status code
"""
from enums import Status


def test_status_codes():
    """
        This is a basic assertion method for enums/status_code

    """
    assert Status.REG.value == 0
    assert Status.ACT.value == 1
    assert Status.LOK.value == 2
    assert Status.DIS.value == 3
    assert Status.OVR.value == 4
    assert Status.ERR.value == 5
    assert Status.COM.value == 6
