# -*- coding: utf-8 -*-
import json
import logging.config
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi import status, HTTPException

from classes import Settings, ChatbotRequest, ResponseData
from constants import (PROCESSING_TIME, CONTENT_TYPE, APPLICATION_JSON, DESCRIPTION,
                       TAGS_METADATA, TITLE, SUMMARY, TERMS, HUB_MODE, HUB_CHALLENGE, HUB_VERIFY_TOKEN, SUBSCRIBE)
from controller import ctr_create_chatbot, ctr_get_chatbot_from_uuid
from utils import configure_logging


settings = Settings()
log = logging.getLogger(settings.environment)

app = FastAPI(
    openapi_tags=TAGS_METADATA,
    on_startup=[configure_logging],
    title=TITLE,
    description=DESCRIPTION,
    summary=SUMMARY,
    version=settings.version,
    terms_of_service=TERMS,
    contact={
      "name": "Jeremi Alcala",
      "url": "https://jeremi.web-ones.com",
      "email": "jeremialcala@gmail.com",
    },
    license_info={
      "name": "Apache 2.0",
      "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)


@app.middleware("http")
async def interceptor(request: Request, call_next):
    log.info(f"This is a new request {request.client}")
    s_time = time.time()
    body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="INTERNAL SERVER ERROR", data=None)

    response = Response(
        content=body.json(),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )
    try:
        log.info(request.url.path)
        log.info(request.query_params)
        [log.debug(f"Header! -> {hdr}: {val}") for hdr, val in request.headers.items()]
        response = await call_next(request)
    except Exception as e:
        log.error(e.args)
    finally:
        process_time = "{:f}".format(time.time() - s_time)
        response.headers[PROCESSING_TIME] = str(process_time)
        return response


@app.post(path="/bot", tags=["Bot"], )
async def create_chatbot(chatbot: ChatbotRequest):
    log.info(f"this is the start of a new chatbot name: {chatbot.name}")
    try:
        response = await ctr_create_chatbot(chatbot)
        log.info(f"this is the end, the response go with code:{response.status_code}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}", tags=["Chat"])
async def verify(request: Request, bot_id):
    log.info(f"this is a chatbot verification request: {bot_id}")
    try:
        _bot = await ctr_get_chatbot_from_uuid(bot_id)

        if _bot.status_code != status.HTTP_200_OK:
            return status.HTTP_404_NOT_FOUND, "HTTP_404_NOT_FOUND"

        """
            Here is the validation that Facebook uses to confirm your webhook!
        """

        if request.query_params.get(HUB_MODE) == SUBSCRIBE:
            if not request.query_params.get(HUB_VERIFY_TOKEN) == settings.verify_token:
                return status.HTTP_403_FORBIDDEN, "HTTP_403_FORBIDDEN"
            if request.query_params.get(HUB_CHALLENGE):
                return status.HTTP_200_OK, request.query_params[HUB_CHALLENGE]

        log.info(f"this is the methods end! it was successful")
        return status.HTTP_200_OK, "HTTP_200_OK"
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}", tags=["Chat"])
async def message_processor(request: Request, bot_id):
    pass

