# -*- coding: utf8 -*-
"""
    Loading and rotating the Meta credentials of a chatbot. They go in through here and do not come out: the
    answer only says which ones are loaded.
"""
import logging

from fastapi import status
from fastapi.responses import JSONResponse

from classes import BotCredentialsRequest, ResponseData, Settings
from crypto.key_service import KeyServiceUnavailable
from repository import NotFound, TenantRepository

__all__ = ["ctr_set_bot_credentials"]

settings = Settings()
log = logging.getLogger(settings.environment)


def _answer(code: int, message: str, data=None) -> JSONResponse:
    body = ResponseData(code=code, message=message, data=data)
    return JSONResponse(status_code=code, content=body.model_dump(mode="json", exclude_none=True))


async def ctr_set_bot_credentials(repo: TenantRepository, bot_id: str, request: BotCredentialsRequest) -> JSONResponse:
    try:
        bot = repo.set_bot_credentials(bot_id, facebookToken=request.facebookToken,
                                       whatsappToken=request.whatsappToken, appSecret=request.appSecret)
    except NotFound:
        return _answer(status.HTTP_404_NOT_FOUND, "This chatbot was not found")
    except KeyServiceUnavailable as e:
        log.error(f"Key service unavailable: {e}")
        return _answer(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE UNAVAILABLE")
    log.info(f"Credentials loaded for chatbot {bot.uuid}")
    return _answer(status.HTTP_200_OK, "Process completed successfully",
                   {"uuid": str(bot.uuid), "credentials": bot.chatbot_info()["credentials"]})
