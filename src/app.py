# -*- coding: utf-8 -*-
import json
import logging.config
import time
import asyncio

from starlette.concurrency import iterate_in_threadpool
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from inspect import currentframe
from uuid import UUID, uuid4
from classes import (Settings, ChatbotRequest, ResponseData, FacebookRequest, ChatbotPhoneRequest, EventTransport,
                     RulesRequest, BotResponse, IntentRequest, ChatBot, ClientRequest, SigningKeyRequest,
                     OwnedKeyRequest, BotCredentialsRequest, ContactSearchRequest)
from constants import (PROCESSING_TIME, CONTENT_TYPE, APPLICATION_JSON, DESCRIPTION,
                       TAGS_METADATA, TITLE, SUMMARY, TERMS, HUB_MODE, HUB_CHALLENGE, HUB_VERIFY_TOKEN, SUBSCRIBE,
                       CONTACT, HUB_SIGNATURE)

from controller import (ctr_create_chatbot, ctr_get_chatbot_from_uuid, ctr_process_messages, ctr_add_phone_chatbot,
                        ctr_get_chatbot_phones, ctr_create_event, ctr_get_chatbot_rules_from_uuid,
                        ctr_create_chatbot_rules, ctr_create_intent, ctr_get_intents, ctr_get_intent,
                        ctr_update_intent, ctr_delete_intent, ctr_get_bot_tools,
                        ctr_register_client, ctr_list_clients, ctr_get_client, ctr_add_signing_key,
                        ctr_add_own_signing_key,
                        ctr_remove_signing_key, ctr_gateway_keys, ctr_set_bot_credentials, ctr_list_contacts,
                        ctr_search_contacts, ctr_export_contact, ctr_delete_contact, ctr_delete_chatbot,
                        ctr_delete_client, RETRY_LATER, ctr_get_bot_tokens, ctr_add_service_key,
                        ctr_remove_service_key)
from controller.incoming import NotUnderstood, read_notification

from auth.gateway_keys import GatewayKeys
from auth.principal import Principal, authenticate
from auth.tokens import InvalidToken
from crypto.fields import NotEncrypted
from crypto.key_service import KeyServiceUnavailable, OpenBaoKeyService
from enums import Role
from repository import (TenantRepository, BotSecrets, NotFound, find_webhook_bot, data_keys, erasures,
                        database_failed)
from utils import BodySizeLimit, configure_logging, describe, is_valid_signature, looks_like_signature, secrets_match

settings = Settings()
log = logging.getLogger(settings.environment)


# Read once, at start: without the gateway's key pair no client could authenticate, so the app does not start.
GATEWAY_KEYS = GatewayKeys.load(settings.gateway_keys_file)

# The key service is only reached when a data key is needed: the app starts without it, and until it answers
# whatever needs a key gets a 503. Outside development it must be reached over TLS.
if not settings.andvari_addr.startswith("https://") and settings.environment != "development":
    raise ValueError("ANDVARI_ADDR must be an https address")
data_keys.configure(OpenBaoKeyService(settings.andvari_addr, settings.andvari_role_id,
                                      settings.andvari_secret_id_file, settings.andvari_ca_file))

# Every deletion is written down here before it is made. Like the key service, it is only reached when needed.
erasures.configure(settings.erasures_dir)

bearer = HTTPBearer(auto_error=False, bearerFormat="JWE",
                    description="A JWT signed by the client (ES256), inside a JWE encrypted to the gateway "
                                "(RSA-OAEP-256, A256CBC-HS512). It lasts 60 seconds at most and is valid once.")


# Everything the response engine may call with the key it holds for a client. A route that is not here is
# closed to it, and so is any route added later until it is written down here.
SERVICE_ROUTES = {
    ("GET", "/gateway/keys"),
    ("GET", "/chat/{bot_id}/rules"),
    ("GET", "/chat/{bot_id}/tools"),
    ("GET", "/chat/{bot_id}/tokens"),
}


async def get_principal(request: Request,
                        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    """
        Everything but the two Meta webhook routes and the health check depends on this. The answer to a token
        that is not accepted is always the same 401: the reason only goes to the log.
    """
    try:
        principal = authenticate(credentials.credentials if credentials else None, GATEWAY_KEYS,
                                 settings.gateway_audience)
    except InvalidToken as e:
        log.warning(f"Rejected a request: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HTTP_401_UNAUTHORIZED",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    route = (METHODS.get(request.method), getattr(request.scope.get("route"), "path", None))
    if principal.role is Role.SERVICE and route not in SERVICE_ROUTES:
        log.warning(f"The response engine was denied a route with its key for client {principal.client_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    return principal


async def require_service(principal: Principal = Depends(get_principal)) -> Principal:
    """What only the response engine gets. A client does not get it with its own key, nor does the operator."""
    if principal.role is not Role.SERVICE:
        log.warning(f"Client {principal.client_id} was denied a route of the response engine")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    return principal


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


def database_unavailable(error: Exception) -> HTTPException:
    """What Meta is answered when the database does not do its part: a 503, so that it sends it again."""
    log.error(f"The database is unavailable: {describe(error)}")
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HTTP_503_SERVICE_UNAVAILABLE")


async def get_webhook_bot(bot_id: str) -> ChatBot:
    try:
        # A malformed id is turned away before it costs a database round trip.
        return find_webhook_bot(bot_id)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTTP_404_NOT_FOUND")
    except Exception as e:
        if not database_failed(e):
            raise
        raise database_unavailable(e) from None


def webhook_secrets(bot: ChatBot) -> BotSecrets:
    """
        What Meta's verification and signature are checked against, opened with the key of the client that
        owns the chatbot. Without the key there is nothing to check against, and the answer is never to let
        the request through.
    """
    try:
        return TenantRepository(bot.clientId).bot_secrets(bot)
    except KeyServiceUnavailable as e:
        log.error(f"Key service unavailable: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="HTTP_503_SERVICE_UNAVAILABLE") from None
    except NotEncrypted:
        # Secrets written by hand, or from before they were encrypted and the migration has not reached them.
        log.error(f"Chatbot {bot.uuid} holds secrets that are not encrypted: run the encryption migration")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTTP_404_NOT_FOUND") from None
    except NotFound:
        # The client that owned it is gone, and its key with it: there is nobody to receive this for.
        log.error(f"Chatbot {bot.uuid} belongs to a client that does not exist")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTTP_404_NOT_FOUND") from None
    except Exception as e:
        if not database_failed(e):
            raise
        raise database_unavailable(e) from None


async def get_signed_webhook_bot(request: Request, _bot: ChatBot = Depends(get_webhook_bot)) -> ChatBot:
    """
        Meta signs every notification with the App Secret, over the body exactly as it was sent. A request without
        anything that could be a signature is turned away before the secrets of the chatbot are opened: otherwise
        anybody who knows its address makes the gateway ask the key service for its client's key.
    """
    header = request.headers.get(HUB_SIGNATURE)
    if not looks_like_signature(header):
        log.warning(f"Rejected webhook for chatbot {_bot.uuid}: missing or invalid {HUB_SIGNATURE}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    secret = webhook_secrets(_bot).app_secret or settings.facebook_app_secret
    if not is_valid_signature(secret, await request.body(), header):
        log.warning(f"Rejected webhook for chatbot {_bot.uuid}: missing or invalid {HUB_SIGNATURE}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")
    return _bot


def documentation(environment: str) -> dict:
    """
        The interactive documentation, and the schema it reads, only in development: anywhere else they show every
        route and model to whoever finds the address. The contract is docs/02-design/contracts/openapi.yaml.
    """
    if environment == "development":
        return {}
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(
    **documentation(settings.environment),
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


# No request may be larger than this: it is the largest notification Meta sends, and nothing a client sends comes
# close. Added before the interceptor, so that the interceptor is outside it and logs what is turned away.
MAX_BODY_BYTES = 3 * 1024 * 1024
app.add_middleware(BodySizeLimit, limit=MAX_BODY_BYTES)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, error: RequestValidationError):
    """
        Says where a request is wrong and why, never with what: by default the answer repeats what was sent,
        and what is sent here are credentials, phone numbers and messages.
    """
    detail = [{"type": item["type"], "loc": list(item["loc"]), "msg": item["msg"]} for item in error.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail})


# The method of a request as the log names it: one of these, never the text that was sent.
METHODS = {method: method for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")}


def request_line(request: Request) -> str:
    """
        A request as it goes to the log: the route it matched, as it is declared, and the identifiers in its
        address that are well formed. Never the address as it was sent, nor its query string: they carry
        verification tokens, and whatever a caller wants to plant in the log.
    """
    identifiers = []
    for value in request.scope.get("path_params", {}).values():
        try:
            identifiers.append(str(UUID(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    route = getattr(request.scope.get("route"), "path", "no route")
    return " ".join([METHODS.get(request.method, "OTHER"), route, *identifiers])


@app.middleware("http")
async def interceptor(request: Request, call_next):
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
        # asyncio.ensure_future(ctr_create_event(event))

        request.state.event_id = None

        response = await call_next(request)
    except Exception as e:
        log.error(describe(e))
    finally:
        process_time = "{:f}".format(time.time() - s_time)
        response.headers[PROCESSING_TIME] = str(process_time)
        # The one line a request leaves, written once it is known which route it was.
        log.info(f"{request_line(request)} code:{response.status_code} time: {process_time}")
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
    try:
        response = await ctr_create_chatbot(repo, request=chatbot, eventId=request.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.delete(path="/bot/{bot_id}", tags=["Bot"], response_model=ResponseData)
async def delete_chatbot(bot_id: str, repo: TenantRepository = Depends(get_repository)):
    """
        Deletes a chatbot and everything stored for it: its contacts, phones, rules and intents. It cannot be
        undone. From then on its webhook answers 404: the subscription in Meta has to be removed as well.
    """
    return await ctr_delete_chatbot(repo, bot_id)


@app.get(path="/chat/{bot_id}", tags=["Chat"])
async def verify(request: Request, bot_id, _bot: ChatBot = Depends(get_webhook_bot)):
    log.info(f"Starting: {currentframe().f_code.co_name}")

    """
        Here is the validation that Facebook uses to confirm your webhook!
    """

    challenge = request.query_params.get(HUB_CHALLENGE)
    if (request.query_params.get(HUB_MODE) != SUBSCRIBE or not challenge
            or not secrets_match(webhook_secrets(_bot).verify_token, request.query_params.get(HUB_VERIFY_TOKEN))):
        log.warning(f"Rejected webhook verification for chatbot {_bot.uuid}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HTTP_403_FORBIDDEN")

    log.info(f"Ending: {currentframe().f_code.co_name}")
    return PlainTextResponse(challenge)


# The body is not declared as a parameter: it would be parsed before the signature is checked. It is read by
# hand once the signature is good, and this is only what the contract says of it.
NOTIFICATION = {"requestBody": {"required": True, "content": {"application/json": {
    "schema": FacebookRequest.model_json_schema()}}}}


@app.post(path="/chat/{bot_id}", tags=["Chat"], openapi_extra=NOTIFICATION)
async def message_processor(request: Request, bot_id, _bot: ChatBot = Depends(get_signed_webhook_bot)):
    """
        What Meta is answered. 403 without a good signature, before anything of the body is read. 200 for
        everything it signed, also for what the service does not understand or cannot process: asking for it
        again would not change it, and Meta stops delivering to a webhook that keeps failing. 503 only when
        something the service needs is not there: then Meta sends it again later.
    """
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        notification = read_notification(await request.body())
    except NotUnderstood as e:
        log.warning(f"A signed notification for chatbot {_bot.uuid} was not understood: {e}")
        return "HTTP_200_OK", status.HTTP_200_OK
    try:
        await ctr_process_messages(req=notification, _bot=_bot)
    except RETRY_LATER:
        # Anything but a 200 makes Meta deliver the notification again later.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HTTP_503_SERVICE_UNAVAILABLE")

    log.info(f"Ending: {currentframe().f_code.co_name}")
    return "HTTP_200_OK", status.HTTP_200_OK


@app.post(path="/chat/{bot_id}/phones", tags=["Chat"])
async def add_whatsapp_phone(bot_id: str, chatbot: ChatbotPhoneRequest, request: Request,
                             repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_add_phone_chatbot(repo, bot_uuid=bot_id, req=chatbot, eventId=request.state.event_id)

        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        log.error(describe(e))
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/phones", tags=["Chat"])
async def get_chatbot_phones(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
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
    try:
        response = await ctr_get_chatbot_from_uuid(repo, bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.put(path="/chat/{bot_id}/credentials", tags=["Chat"], response_model=ResponseData)
async def set_chatbot_credentials(bot_id: str, credentials: BotCredentialsRequest,
                                  repo: TenantRepository = Depends(get_repository)):
    """
        Loads or rotates the Meta credentials of a chatbot: the page token, the WhatsApp token and the App
        Secret. The ones sent replace the stored ones. The answer says which are loaded, never their values.
    """
    return await ctr_set_bot_credentials(repo, bot_id, credentials)


@app.get(path="/chat/{bot_id}/contacts", tags=["Contacts"], response_model=ResponseData)
async def list_contacts(bot_id: str, offset: int = Query(default=0, ge=0),
                        limit: int = Query(default=100, ge=1, le=500),
                        repo: TenantRepository = Depends(get_repository)):
    """The contacts of a chatbot, oldest first, a page at a time, with everything stored about each."""
    return await ctr_list_contacts(repo, bot_id, offset, limit)


@app.get(path="/chat/{bot_id}/contacts/{contact_id}", tags=["Contacts"], response_model=ResponseData)
async def export_contact(bot_id: str, contact_id: str, repo: TenantRepository = Depends(get_repository)):
    """Everything the service stores about a contact. It does not keep the messages: those go to the queue."""
    return await ctr_export_contact(repo, bot_id, contact_id)


@app.delete(path="/chat/{bot_id}/contacts/{contact_id}", tags=["Contacts"], response_model=ResponseData)
async def delete_contact(bot_id: str, contact_id: str, repo: TenantRepository = Depends(get_repository)):
    """
        Deletes a contact of a chatbot. It cannot be undone. If the same person writes again, it is stored
        again as a new contact.
    """
    return await ctr_delete_contact(repo, bot_id, contact_id)


@app.post(path="/contacts/search", tags=["Contacts"], response_model=ResponseData)
async def search_contacts(search: ContactSearchRequest, repo: TenantRepository = Depends(get_repository)):
    """
        Finds a person among the contacts of all the chatbots of the client, by WhatsApp number or by
        Messenger id. It is how a request from somebody for their data starts.
    """
    return await ctr_search_contacts(repo, search)


@app.get(path="/chat/{bot_id}/tokens", tags=["Chat"], response_model=ResponseData)
async def get_chatbot_tokens(bot_id: str, engine: Principal = Depends(require_service)):
    """
        The Meta tokens of a chatbot, for the response engine to send its answers with. Only the engine gets
        them, with the key it holds for the client that owns the chatbot, and every time it does is logged.
    """
    return await ctr_get_bot_tokens(TenantRepository(engine.client_id), bot_id, engine)


@app.get(path="/chat/{bot_id}/rules", tags=["Chat"])
async def get_chatbot_rules(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")

    try:
        response = await ctr_get_chatbot_rules_from_uuid(repo, bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/rules", tags=["Chat"])
async def add_chatbot_rule(bot_id, req: Request, rules: RulesRequest,
                           repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_create_chatbot_rules(repo, request=rules, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.post(path="/chat/{bot_id}/intents", tags=["Intents"])
async def add_chatbot_intent(bot_id, req: Request, intent: IntentRequest,
                             repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_create_intent(repo, request=intent, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/intents", tags=["Intents"])
async def list_chatbot_intents(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_get_intents(repo, bot_id=bot_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def get_chatbot_intent(bot_id, intent_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_get_intent(repo, bot_id=bot_id, intent_id=intent_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.put(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def update_chatbot_intent(bot_id, intent_id, req: Request, intent: IntentRequest,
                                repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_update_intent(repo, request=intent, bot_id=bot_id, intent_id=intent_id,
                                           eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.delete(path="/chat/{bot_id}/intents/{intent_id}", tags=["Intents"])
async def delete_chatbot_intent(bot_id, intent_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
    try:
        response = await ctr_delete_intent(repo, bot_id=bot_id, intent_id=intent_id, eventId=req.state.event_id)
        log.info(f"Ending: {currentframe().f_code.co_name}")
        return response
    except Exception as e:
        raise Exception(e.args)


@app.get(path="/chat/{bot_id}/tools", tags=["Intents"])
async def get_chatbot_tools(bot_id, req: Request, repo: TenantRepository = Depends(get_repository)):
    log.info(f"Starting: {currentframe().f_code.co_name}")
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
async def add_my_key(key: OwnedKeyRequest, principal: Principal = Depends(get_principal)):
    """
        A client registers a second public key to rotate: both work until it removes the old one. The new key
        signs a proof for the token of this same request, so nobody registers a key they cannot sign with.
    """
    return await ctr_add_own_signing_key(principal, key)


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


@app.delete(path="/clients/{client_id}", tags=["Clients"], response_model=ResponseData)
async def delete_client(client_id: str, _operator: Principal = Depends(require_operator)):
    """
        The operator takes a client off the service: its keys stop working at once, and its chatbots, with
        everything stored for them, and its data key are deleted. It cannot be undone.
    """
    return await ctr_delete_client(client_id)


@app.post(path="/clients/{client_id}/keys", tags=["Clients"], response_model=ResponseData)
async def add_client_key(client_id: str, key: SigningKeyRequest, _operator: Principal = Depends(require_operator)):
    return await ctr_add_signing_key(client_id, key)


@app.post(path="/clients/{client_id}/service-keys", tags=["Clients"], response_model=ResponseData)
async def add_service_key(client_id: str, key: SigningKeyRequest, _operator: Principal = Depends(require_operator)):
    """
        The operator lets the response engine act for a client: it registers the public key the engine signs
        with for that client. With it the engine reaches the chatbots of that client and of nobody else.
    """
    return await ctr_add_service_key(client_id, key)


@app.delete(path="/clients/{client_id}/service-keys/{kid}", tags=["Clients"], response_model=ResponseData)
async def remove_service_key(client_id: str, kid: str, _operator: Principal = Depends(require_operator)):
    """Takes the response engine's key for a client away: it stops reaching that client's chatbots at once."""
    return await ctr_remove_service_key(client_id, kid)


@app.delete(path="/clients/{client_id}/keys/{kid}", tags=["Clients"], response_model=ResponseData)
async def remove_client_key(client_id: str, kid: str, _operator: Principal = Depends(require_operator)):
    """Revoking a key is deleting it: the tokens signed with it stop being accepted at once."""
    return await ctr_remove_signing_key(client_id, kid, keep_one=False)
