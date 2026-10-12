# -*- coding: utf-8 -*-
import json
import logging.config
import time
import asyncio

from starlette.concurrency import iterate_in_threadpool
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi import status
from fastapi.responses import PlainTextResponse
from inspect import currentframe
from uuid import uuid4
from classes import (Settings, ChatbotRequest, ResponseData, FacebookRequest, ChatbotPhoneRequest, EventTransport,
                     RulesRequest, BotResponse, IntentRequest, ChatBot)
from constants import (PROCESSING_TIME, CONTENT_TYPE, APPLICATION_JSON, DESCRIPTION,
                       TAGS_METADATA, TITLE, SUMMARY, TERMS, HUB_MODE, HUB_CHALLENGE, HUB_VERIFY_TOKEN, SUBSCRIBE,
                       CONTACT, API_KEY, HUB_SIGNATURE)

from controller import (ctr_create_chatbot, ctr_get_chatbot_from_uuid, ctr_process_messages, ctr_add_phone_chatbot,
                        ctr_get_chatbot_phones, ctr_create_event, ctr_get_chatbot_rules_from_uuid,
                        ctr_create_chatbot_rules, ctr_create_intent, ctr_get_intents, ctr_get_intent,
                        ctr_update_intent, ctr_delete_intent, ctr_get_bot_tools, BrokerUnavailable)

from repository import TenantRepository, NotFound, find_webhook_bot, operator_client
from utils import configure_logging, is_valid_signature, secrets_match

settings = Settings()
log = logging.getLogger(settings.environment)


async def get_repository(request: Request) -> TenantRepository:
    """
        Every management endpoint depends on this: only the two Meta webhook routes are public. What it hands
        over is the repository of the authenticated client, the only way those endpoints have to reach data.

        Until clients authenticate with their own tokens the only caller is the operator, with the admin key,
        and it works on its own client.
    """
    if not secrets_match(settings.admin_api_key, request.headers.get(API_KEY)):
        log.warning(f"Rejected {request.method} {request.url.path}: missing or wrong admin credential")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HTTP_401_UNAUTHORIZED")
    return TenantRepository(operator_client().uuid)


async def get_webhook_bot(bot_id: str) -> ChatBot:
    try:
        # A malformed id is turned away before it costs a database round trip.
        return find_webhook_bot(bot_id)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTTP_404_NOT_FOUND")


async def get_signed_webhook_bot(request: Request, _bot: ChatBot = Depends(get_webhook_bot)) -> ChatBot:
    """
        Meta signs every notification with the App Secret, over the body exactly as it was sent.
    """
    secret = _bot.appSecret or settings.facebook_app_secret
    if not is_valid_signature(secret, await request.body(), request.headers.get(HUB_SIGNATURE)):
        log.warning(f"Rejected webhook for chatbot {_bot.uuid}: missing or invalid {HUB_SIGNATURE}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    return _bot


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
        # The server does not always know the peer (unix sockets, test clients): that must not fail the request.
        origen=f"address: {request.client.host} port: {request.client.port}" if request.client else "unknown"
    )

    response = Response(
        content=body.json(exclude_none=True),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )

    try:
        # Query strings, headers and bodies stay out of the log: they carry verify tokens, API keys and signatures.
        log.info(request.url.path)
        # asyncio.ensure_future(ctr_create_event(event))

        request.state.event_id = None

        response = await call_next(request)
    except Exception as e:
        log.error(e.__str__())
    finally:
        process_time = "{:f}".format(time.time() - s_time)
        response.headers[PROCESSING_TIME] = str(process_time)
        log.info(f"Ending: {currentframe().f_code.co_name} code:{response.status_code} time: {process_time}")
    return response


@app.get(path="/health", tags=["Health"])
async def health():
    """
        Liveness only: it answers without touching MongoDB or RabbitMQ, so a slow dependency does not get a
        healthy container restarted or rolled back.
    """
    return {"status": "ok"}


@app.post(path="/bot", tags=["Bot"], response_model=BotResponse)
async def create_chatbot(chatbot: ChatbotRequest, request: Request,
                         repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is the start of a new chatbot name: {chatbot.name}")
    try:
        log.info(request.state.__dict__)
        response = await ctr_create_chatbot(repo, request=chatbot, eventId=request.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}", tags=["Chat"])
async def verify(request: Request, bot_id, _bot: ChatBot = Depends(get_webhook_bot)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is a chatbot verification request: {bot_id}")

    """
        Here is the validation that Facebook uses to confirm your webhook!
    """

    challenge = request.query_params.get(HUB_CHALLENGE)
    if (request.query_params.get(HUB_MODE) != SUBSCRIBE or not challenge
            or not secrets_match(_bot.verifyToken, request.query_params.get(HUB_VERIFY_TOKEN))):
        log.warning(f"Rejected webhook verification for chatbot {bot_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")

    log.info(f"Ending: {currentframe().f_code.co_name}")
    return PlainTextResponse(challenge)


@app.post(path="/chat/{bot_id}", tags=["Chat"])
async def message_processor(fb_request: FacebookRequest, bot_id, _bot: ChatBot = Depends(get_signed_webhook_bot)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"this is a new message for this chatbot: {bot_id}")
    try:
        await ctr_process_messages(req=fb_request, _bot=_bot)
    except BrokerUnavailable:
        # Anything but a 200 makes Meta deliver the notification again later.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HTTP_503_SERVICE_UNAVAILABLE")

    log.info(f"Ending: {currentframe().f_code.co_name}")
    return "HTTP_200_OK", status.HTTP_200_OK


@app.post(path="/chat/{bot_id}/phones", tags=["Chat"])
async def add_whatsapp_phone(bot_id: str, chatbot: ChatbotPhoneRequest, request: Request,
                             repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} or this chatbot: {bot_id}")
    try:
        response = await ctr_add_phone_chatbot(repo, bot_uuid=bot_id, req=chatbot, eventId=request.state.event_id)

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        log.error(e.__str__())
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/phones", tags=["Chat"])
async def get_chatbot_phones(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Starting get_chatbot_phones for this chatbot: {bot_id}")
    try:
        response = await ctr_get_chatbot_phones(repo, bot_uuid=bot_id,
                                                environment=req.query_params.get("environment"))

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/info", tags=["Chat"])
async def get_chatbot_info(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    log.info(f"Starting get_chatbot_phones for this chatbot: {bot_id}")
    try:
        response = await ctr_get_chatbot_from_uuid(repo, bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/rules", tags=["Chat"])
async def get_chatbot_rules(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")

    try:
        response = await ctr_get_chatbot_rules_from_uuid(repo, bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/rules", tags=["Chat"])
async def add_chatbot_rule(bot_id, req: Request, rules: RulesRequest,
                           repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")
    try:
        response = await ctr_create_chatbot_rules(repo, request=rules, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/intents", tags=["Intents"])
async def add_chatbot_intent(bot_id, req: Request, intent: IntentRequest,
                             repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")
    try:
        response = await ctr_create_intent(repo, request=intent, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/intents", tags=["Intents"])
async def list_chatbot_intents(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")
    try:
        response = await ctr_get_intents(repo, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def get_chatbot_intent(bot_id, intent_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this intent: {intent_id}")
    try:
        response = await ctr_get_intent(repo, bot_id=bot_id, intent_id=intent_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.put(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def update_chatbot_intent(bot_id, intent_id, req: Request, intent: IntentRequest,
                                repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this intent: {intent_id}")
    try:
        response = await ctr_update_intent(repo, request=intent, bot_id=bot_id, intent_id=intent_id,
                                           eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.delete(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def delete_chatbot_intent(bot_id, intent_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this intent: {intent_id}")
    try:
        response = await ctr_delete_intent(repo, bot_id=bot_id, intent_id=intent_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/tools", tags=["Intents"])
async def get_chatbot_tools(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name} for this chatbot: {bot_id}")
    try:
        response = await ctr_get_bot_tools(repo, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)

