"""
    This is test module for enums/Response
"""
from enums import ResponseCodes


def test_response_codes():
    """
        Basic assertion for all response codes/

    """
    assert ResponseCodes.AOK.value == 200
    assert ResponseCodes.CRD.value == 201
    assert ResponseCodes.UPD.value == 202
    assert ResponseCodes.NOK.value == 400
    assert ResponseCodes.FOR.value == 403
    assert ResponseCodes.NOF.value == 404
    assert ResponseCodes.ERR.value == 500
