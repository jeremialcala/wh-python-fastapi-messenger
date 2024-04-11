# -*- coding: utf-8 -*-
import json
import logging.config
import time
import asyncio

from starlette.concurrency import iterate_in_threadpool
from fastapi import FastAPI, Request, Response
from fastapi import status
from inspect import currentframe
from uuid import uuid4
from classes import (Settings, ChatbotRequest, ResponseData, FacebookRequest, ChatbotPhoneRequest, EventTransport,
                     RulesRequest, BotResponse)
from constants import (PROCESSING_TIME, CONTENT_TYPE, APPLICATION_JSON, DESCRIPTION,
                       TAGS_METADATA, TITLE, SUMMARY, TERMS, HUB_MODE, HUB_CHALLENGE, HUB_VERIFY_TOKEN, SUBSCRIBE,
                       CONTACT)

from controller import (ctr_create_chatbot, ctr_get_chatbot_from_uuid, ctr_process_messages, ctr_add_phone_chatbot,
                        ctr_get_chatbot_phones, ctr_create_event, ctr_get_chatbot_rules_from_uuid,
                        ctr_create_chatbot_rules)

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
    contact=CONTACT,
    license_info={
      "name": "Apache 2.0",
      "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)


@app.middleware("http")
async def interceptor(request: Request, call_next):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"This is a new request {request.client}")
    s_time = time.time()
    body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="INTERNAL SERVER ERROR", data=None)

    event = EventTransport(
        uuid=uuid4(),
        resource=request.url.path,
        operation=request.method,
        origen=f"address: {request.client.host} port: {request.client.port}"
    )

    response = Response(
        content=body.json(exclude_none=True),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )
    response_body = b""
    try:
        log.info(request.url.path)
        log.info(request.query_params)
        # asyncio.ensure_future(ctr_create_event(event))

        request.state.event_id = None
        [log.debug(f"Header! -> {hdr}: {val}") for hdr, val in request.headers.items()]

        response = await call_next(request)

        log.info(f"response_body= {response[0].decode()}")
    except Exception as e:
        log.error(e.__str__())
    finally:
        process_time = "{:f}".format(time.time() - s_time)
        response.headers[PROCESSING_TIME] = str(process_time)
        [log.debug(f"Header! -> {hdr}: {val}") for hdr, val in response.headers.items()]
        log.info(f"Ending: {currentframe().f_code.co_name} code:{response.status_code} time: {process_time}")
        return response


@app.post(path="/bot", tags=["Bot"], response_model=BotResponse)
async def create_chatbot(chatbot: ChatbotRequest, request: Request):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is the start of a new chatbot name: {chatbot.name}")
    try:
        log.info(request.state.__dict__)
        response = await ctr_create_chatbot(request=chatbot, eventId=request.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}", tags=["Chat"])
async def verify(request: Request, bot_id):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is a chatbot verification request: {bot_id}")
    try:
        _bot = await ctr_get_chatbot_from_uuid(_uuid=bot_id, eventId=request.state.event_id)

        if _bot.status_code != status.HTTP_200_OK:
            return status.HTTP_404_NOT_FOUND, "HTTP_404_NOT_FOUND"

        _bot_info = json.loads(_bot.body)

        """
            Here is the validation that Facebook uses to confirm your webhook!
        """

        if request.query_params.get(HUB_MODE) == SUBSCRIBE:
            if not request.query_params.get(HUB_VERIFY_TOKEN) == _bot_info["data"]["verifyToken"]:
                return status.HTTP_403_FORBIDDEN, "HTTP_403_FORBIDDEN"
            if request.query_params.get(HUB_CHALLENGE):
                return request.query_params[HUB_CHALLENGE], status.HTTP_200_OK

        log.info(f"Ending: {currentframe().f_code.co_name}s")
        return "HTTP_200_OK", status.HTTP_200_OK
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}", tags=["Chat"])
async def message_processor(fb_request: FacebookRequest, request: Request, bot_id):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is a chatbot verification request: {bot_id}")
    try:
        _bot = await ctr_get_chatbot_from_uuid(_uuid=bot_id, eventId=request.state.event_id)

        if _bot.status_code != status.HTTP_200_OK:
            return "HTTP_404_NOT_FOUND", status.HTTP_404_NOT_FOUND

        asyncio.ensure_future(ctr_process_messages(req=fb_request, _bot_info=bot_id))

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return "HTTP_200_OK", status.HTTP_200_OK
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/phones", tags=["Chat"])
async def add_whatsapp_phone(bot_id: str, chatbot: ChatbotPhoneRequest, request: Request):
    log.info(f"Starting: {currentframe().f_code.co_name} or this chatbot: {bot_id}")
    try:
        _bot = await ctr_get_chatbot_from_uuid(_uuid=bot_id, eventId=request.state.event_id)

        if _bot.status_code != status.HTTP_200_OK:
            return "HTTP_404_NOT_FOUND", status.HTTP_404_NOT_FOUND

        response = await ctr_add_phone_chatbot(bot_uuid=bot_id, req=chatbot, eventId=request.state.event_id)

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        log.error(e.__str__())
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/phones", tags=["Chat"])
async def get_chatbot_phones(bot_id, req: Request):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Starting get_chatbot_phones for this chatbot: {bot_id}")
    try:
        _bot = await ctr_get_chatbot_from_uuid(bot_id, eventId=req.state.event_id)

        if _bot.status_code != status.HTTP_200_OK:
            return "HTTP_404_NOT_FOUND", status.HTTP_404_NOT_FOUND

        response = await ctr_get_chatbot_phones(bot_uuid=bot_id, environment=req.query_params.get("environment"))

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/info", tags=["Chat"])
async def get_chatbot_info(bot_id, req: Request):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Starting get_chatbot_phones for this chatbot: {bot_id}")
    try:
        response = await ctr_get_chatbot_from_uuid(bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/rules", tags=["Chat"])
async def get_chatbot_rules(bot_id, req: Request):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")

    try:
        response = await ctr_get_chatbot_rules_from_uuid(bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/rules", tags=["Chat"])
async def add_chatbot_rule(bot_id, req: Request, rules: RulesRequest):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")
    try:
        response = await ctr_create_chatbot_rules(request=rules, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)

