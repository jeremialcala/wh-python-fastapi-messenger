# -*- coding: utf-8 -*-
"""
    Encrypts what was stored in clear before each client had a data key: the secrets of the chatbots, the numbers
    of their phones and the numbers of their contacts, which also get their blind index. Until this runs, a chatbot
    with secrets in clear answers 404 on the webhook and its contacts are not found again.

    Run migrations.assign_operator_client first: a document without a client has no key to be encrypted with,
    and it is left as it is and counted apart.

    It only reports what it would do unless it is called with --apply, and running it twice changes nothing.

        python -m migrations.encrypt_client_data            # report
        python -m migrations.encrypt_client_data --apply    # write
"""
import sys

from mongoengine.errors import SaveConditionError

from classes import ChatBot, ChatbotPhone, Contact
from crypto.fields import is_encrypted
from repository import data_keys
from repository.tenant import BOT_SECRETS, PHONE_FIELDS

TARGETS = ((ChatBot, BOT_SECRETS), (ChatbotPhone, PHONE_FIELDS), (Contact, ("waId",)))


def in_clear(document, fields) -> list:
    return [field for field in fields if getattr(document, field) is not None and not is_encrypted(getattr(document, field))]


def run(apply: bool) -> dict:
    report = {}
    for collection, fields in TARGETS:
        pending = without_client = 0
        for document in collection.objects:
            clear = in_clear(document, fields)
            if not clear:
                continue
            if document.clientId is None:
                without_client += 1
                continue
            pending += 1
            if apply:
                cipher = data_keys.cipher_for(document.clientId)
                for field in clear:
                    value = getattr(document, field)
                    if collection is Contact:
                        document.waIdIndex = cipher.blind_index("Contact.waId", value)
                    setattr(document, field, cipher.encrypt(f"{collection.__name__}.{field}", value))
                try:
                    # It runs while the service does: without the condition, saving a document deleted in the
                    # meantime would bring back part of it, without the client it belonged to.
                    document.save(save_condition={"clientId": document.clientId})
                except SaveConditionError:
                    # Deleted since it was read: there is nothing left to encrypt.
                    continue
        report[collection.__name__] = {"in clear": pending, "without a client": without_client}
    return report


if __name__ == "__main__":
    from classes import Settings
    from crypto.key_service import OpenBaoKeyService

    settings = Settings()
    data_keys.configure(OpenBaoKeyService(settings.andvari_addr, settings.andvari_role_id,
                                          settings.andvari_secret_id_file, settings.andvari_ca_file))
    apply = "--apply" in sys.argv[1:]
    for name, counts in run(apply).items():
        done = " -> encrypted" if apply and counts["in clear"] else ""
        print(f"{name}: {counts['in clear']} with data in clear{done}; {counts['without a client']} without a client")
    if not apply:
        print("Nothing was written. Run again with --apply to encrypt them.")
