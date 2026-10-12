# -*- coding: utf-8 -*-
import json
import logging.config
import time
import asyncio

from starlette.concurrency import iterate_in_threadpool
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi import status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from inspect import currentframe
from uuid import uuid4
from classes import (Settings, ChatbotRequest, ResponseData, FacebookRequest, ChatbotPhoneRequest, EventTransport,
                     RulesRequest, BotResponse, IntentRequest, ChatBot, ClientRequest, SigningKeyRequest)
from constants import (PROCESSING_TIME, CONTENT_TYPE, APPLICATION_JSON, DESCRIPTION,
                       TAGS_METADATA, TITLE, SUMMARY, TERMS, HUB_MODE, HUB_CHALLENGE, HUB_VERIFY_TOKEN, SUBSCRIBE,
                       CONTACT, HUB_SIGNATURE)

from controller import (ctr_create_chatbot, ctr_get_chatbot_from_uuid, ctr_process_messages, ctr_add_phone_chatbot,
                        ctr_get_chatbot_phones, ctr_create_event, ctr_get_chatbot_rules_from_uuid,
                        ctr_create_chatbot_rules, ctr_create_intent, ctr_get_intents, ctr_get_intent,
                        ctr_update_intent, ctr_delete_intent, ctr_get_bot_tools, BrokerUnavailable,
                        ctr_register_client, ctr_list_clients, ctr_get_client, ctr_add_signing_key,
                        ctr_remove_signing_key, ctr_gateway_keys)

from auth.gateway_keys import GatewayKeys
from auth.principal import Principal, authenticate
from auth.tokens import InvalidToken
from enums import Role
from repository import TenantRepository, NotFound, find_webhook_bot
from utils import configure_logging, is_valid_signature, secrets_match

settings = Settings()
log = logging.getLogger(settings.environment)


# Read once, at start: without the gateway's key pair no client could authenticate, so the app does not start.
GATEWAY_KEYS = GatewayKeys.load(settings.gateway_keys_file)

bearer = HTTPBearer(auto_error=False, bearerFormat="JWE",
                    description="A JWT signed by the client (ES256), inside a JWE encrypted to the gateway "
                                "(RSA-OAEP-256, A256CBC-HS512). It lasts 60 seconds at most and is valid once.")


async def get_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    """
        Everything but the two Meta webhook routes and the health check depends on this. The answer to a token
        that is not accepted is always the same 401: the reason only goes to the log.
    """
    try:
        return authenticate(credentials.credentials if credentials else None, GATEWAY_KEYS, settings.gateway_audience)
    except InvalidToken as e:
        log.warning(f"Rejected a request: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HTTP_401_UNAUTHORIZED",
                            headers={"WWW-Authenticate": "Bearer"}) from None


async def get_repository(principal: Principal = Depends(get_principal)) -> TenantRepository:
    """
        What the endpoints of a client get: the repository of whoever is authenticated, the only way they have
        to reach data. The operator is a client too, and reaches its own.
    """
    return TenantRepository(principal.client_id)


async def require_operator(principal: Principal = Depends(get_principal)) -> Principal:
    """The registry of clients is the operator's. What a caller may do comes from its entry, not from the token."""
    if principal.role is not Role.OPERATOR:
        log.warning(f"Client {principal.client_id} was denied an operator endpoint")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    return principal


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


@app.get(path="/gateway/keys", tags=["Clients"], response_model=ResponseData)
async def gateway_keys(_principal: Principal = Depends(get_principal)):
    """
        The audience and the public keys a client encrypts its tokens to. A client that is already in asks here
        for the new key when the gateway rotates its own.
    """
    return await ctr_gateway_keys(GATEWAY_KEYS)


@app.get(path="/keys", tags=["Clients"], response_model=ResponseData)
async def list_my_keys(principal: Principal = Depends(get_principal)):
    return await ctr_get_client(principal.client_id)


@app.post(path="/keys", tags=["Clients"], response_model=ResponseData)
async def add_my_key(key: SigningKeyRequest, principal: Principal = Depends(get_principal)):
    """A client registers a second public key to rotate: both work until it removes the old one."""
    return await ctr_add_signing_key(principal.client_id, key)


@app.delete(path="/keys/{kid}", tags=["Clients"], response_model=ResponseData)
async def remove_my_key(kid: str, principal: Principal = Depends(get_principal)):
    """A client revokes one of its keys. It cannot remove the last one: only the operator can let it back in."""
    return await ctr_remove_signing_key(principal.client_id, kid, keep_one=True)


@app.post(path="/clients", tags=["Clients"], response_model=ResponseData)
async def register_client(client: ClientRequest, _operator: Principal = Depends(require_operator)):
    """
        The operator registers a client with its first public key. The answer carries what the client needs to
        call the service: its identifier, the audience and the gateway's public keys.
    """
    return await ctr_register_client(client, GATEWAY_KEYS)


@app.get(path="/clients", tags=["Clients"], response_model=ResponseData)
async def list_clients(_operator: Principal = Depends(require_operator)):
    return await ctr_list_clients()


@app.post(path="/clients/{client_id}/keys", tags=["Clients"], response_model=ResponseData)
async def add_client_key(client_id: str, key: SigningKeyRequest, _operator: Principal = Depends(require_operator)):
    return await ctr_add_signing_key(client_id, key)


@app.delete(path="/clients/{client_id}/keys/{kid}", tags=["Clients"], response_model=ResponseData)
async def remove_client_key(client_id: str, kid: str, _operator: Principal = Depends(require_operator)):
    """Revoking a key is deleting it: the tokens signed with it stop being accepted at once."""
    return await ctr_remove_signing_key(client_id, kid, keep_one=False)
