# -*- coding: utf-8 -*-
"""
    The management API: what clients, the operator and the response engine call, each with its own token. It runs
    apart from the webhook Meta calls (webhook.py), so that a slow request here never holds a notification up.

        uvicorn app:app
"""
from inspect import currentframe

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.gateway_keys import GatewayKeys
from auth.principal import Principal, authenticate
from auth.tokens import InvalidToken
from classes import (BotCredentialsRequest, BotResponse, ChatbotPhoneRequest, ChatbotRequest, ClientRequest,
                     ContactSearchRequest, IntentRequest, OwnedKeyRequest, ResponseData, RulesRequest,
                     SigningKeyRequest)
from constants import DESCRIPTION, SUMMARY, TAGS_METADATA, TITLE
from controller import (ctr_add_own_signing_key, ctr_add_phone_chatbot, ctr_add_service_key, ctr_add_signing_key,
                        ctr_create_chatbot, ctr_create_chatbot_rules, ctr_create_intent, ctr_delete_chatbot,
                        ctr_delete_client, ctr_delete_contact, ctr_delete_intent, ctr_export_contact,
                        ctr_gateway_keys, ctr_get_bot_tokens, ctr_get_bot_tools, ctr_get_chatbot_from_uuid,
                        ctr_get_chatbot_phones, ctr_get_chatbot_rules_from_uuid, ctr_get_client, ctr_get_intent,
                        ctr_get_intents, ctr_last_turns, ctr_list_clients, ctr_list_contacts, ctr_register_client,
                        ctr_remove_service_key, ctr_remove_signing_key, ctr_search_contacts, ctr_set_bot_credentials,
                        ctr_update_intent)
from enums import Role
from repository import TenantRepository, erasures
from service import METHODS, build, log, settings
from utils import describe

# Only this service authenticates callers and deletes: the webhook runs without either setting.
if not settings.gateway_keys_file:
    raise ValueError("GATEWAY_KEYS_FILE is required")
if not settings.gateway_audience or len(settings.gateway_audience) < 8:
    raise ValueError("GATEWAY_AUDIENCE is required, eight characters at least")

# Read once, at start: without the gateway's key pair no client could authenticate, so the app does not start.
GATEWAY_KEYS = GatewayKeys.load(settings.gateway_keys_file)

# Every deletion is written down here before it is made. It is only reached when needed.
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
    # The coordinator, when its context is gone (RF15). ADR-0022 narrows it to the coordinator's own key in I6.
    ("GET", "/chat/{bot_id}/contacts/{contact_id}/turns"),
}


async def get_principal(request: Request,
                        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    """
        Everything in this service but the health check depends on this. The answer to a token
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


app = build(title=TITLE, summary=SUMMARY, description=DESCRIPTION, openapi_tags=TAGS_METADATA)


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


@app.get(path="/chat/{bot_id}/contacts/{contact_id}/turns", tags=["Contacts"], response_model=ResponseData)
async def get_last_turns(bot_id: str, contact_id: str, engine: Principal = Depends(require_service)):
    """
        The last 10 turns of a conversation, both ways and oldest first: from the tenth last message the contact
        sent, everything after it. For the engine's coordinator, when its context of 24 hours is gone; only the
        engine gets them, with the key it holds for the client that owns the chatbot, and every time it does is
        logged.
    """
    return await ctr_last_turns(TenantRepository(engine.client_id), bot_id, contact_id, engine)


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
