# -*- coding: utf8 -*-
"""
    The people who wrote to a client's chatbots, for the client to answer them when they ask for their data:
    listing them, finding one by number, handing over everything stored about one, and deleting it. Deleting a
    chatbot is here too: it takes its contacts with it.

    Nothing here writes a name, a number or a Messenger id to the log: only the ids the service made up.
"""
import logging
from uuid import UUID

from fastapi import status
from fastapi.responses import JSONResponse

from classes import Contact, ContactSearchRequest, Settings
from crypto.fields import NotEncrypted
from crypto.key_service import KeyServiceUnavailable
from enums import Status
from repository import NotFound, TenantRepository

from .answers import answer

__all__ = ["ctr_list_contacts", "ctr_search_contacts", "ctr_export_contact", "ctr_delete_contact",
           "ctr_delete_chatbot"]

settings = Settings()
log = logging.getLogger(settings.environment)

CONTACT_NOT_FOUND = "This contact was not found"
CHATBOT_NOT_FOUND = "This chatbot was not found"


def contact_info(repo: TenantRepository, contact: Contact) -> dict:
    """Everything the service stores about a contact, with its number opened."""
    return {
        "uuid": str(contact._uuid),
        "botId": str(contact.botId),
        "firstName": contact.firstName,
        "lastName": contact.lastName,
        "profilePic": contact.profilePic,
        "waId": repo.contact_number(contact),
        "fbId": contact.fbId,
        "isAdmin": contact.isAdmin,
        "status": Status(contact.status).name,
        "createdAt": contact.createdAt,
        "statusDate": contact.statusDate,
    }


def _read(found_nothing: str, read) -> JSONResponse:
    """Answers with what `read` returns, or with what went wrong reading it."""
    try:
        return answer(status.HTTP_200_OK, data=read())
    except NotFound:
        return answer(status.HTTP_404_NOT_FOUND, found_nothing)
    except KeyServiceUnavailable as e:
        log.error(f"Key service unavailable: {e}")
        return answer(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE UNAVAILABLE")
    except NotEncrypted:
        # A number from before numbers were encrypted. It is not handed over as it is stored, and an answer
        # without it would pass for everything there is.
        log.error("A contact holds a number that is not encrypted: run the encryption migration")
        return answer(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL SERVER ERROR")


async def ctr_list_contacts(repo: TenantRepository, bot_id: str, offset: int, limit: int) -> JSONResponse:
    def read():
        total, contacts = repo.list_contacts(bot_id, offset, limit)
        return {"total": total, "offset": offset, "limit": limit,
                "contacts": [contact_info(repo, contact) for contact in contacts]}

    return _read(CHATBOT_NOT_FOUND, read)


async def ctr_search_contacts(repo: TenantRepository, request: ContactSearchRequest) -> JSONResponse:
    return _read(CONTACT_NOT_FOUND, lambda: [contact_info(repo, contact) for contact in
                                             repo.find_contacts(wa_id=request.waId, fb_id=request.fbId)])


async def ctr_export_contact(repo: TenantRepository, bot_id: str, contact_id: str) -> JSONResponse:
    return _read(CONTACT_NOT_FOUND, lambda: contact_info(repo, repo.get_contact(bot_id, contact_id)))


async def ctr_delete_contact(repo: TenantRepository, bot_id: str, contact_id: str) -> JSONResponse:
    try:
        deleted = repo.delete_contact(bot_id, contact_id)
    except NotFound:
        return answer(status.HTTP_404_NOT_FOUND, CONTACT_NOT_FOUND)
    # A warning, so that it is kept at the level production logs at: a deletion cannot be undone.
    log.warning(f"Client {repo.client_id} deleted contact {UUID(contact_id)} of chatbot {UUID(bot_id)}: "
                f"{deleted} stored")
    return answer(status.HTTP_200_OK, data={"uuid": str(UUID(contact_id)), "deleted": {"contacts": deleted}})


async def ctr_delete_chatbot(repo: TenantRepository, bot_id: str) -> JSONResponse:
    try:
        deleted = repo.delete_bot(bot_id)
    except NotFound:
        return answer(status.HTTP_404_NOT_FOUND, CHATBOT_NOT_FOUND)
    log.warning(f"Client {repo.client_id} deleted chatbot {UUID(bot_id)}: {deleted}")
    return answer(status.HTTP_200_OK, data={"uuid": str(UUID(bot_id)), "deleted": deleted})
