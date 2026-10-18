# -*- coding: utf8 -*-
from fastapi.responses import JSONResponse

from classes import ResponseData

OK = "Process completed successfully"


def answer(code: int, message: str = OK, data=None) -> JSONResponse:
    """The body every management endpoint answers with, under the same HTTP status it carries."""
    body = ResponseData(code=code, message=message, data=data)
    return JSONResponse(status_code=code, content=body.model_dump(mode="json", exclude_none=True))
