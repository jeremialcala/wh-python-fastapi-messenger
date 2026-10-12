# -*- coding: utf-8 -*-
"""
    Gives an owner to the documents stored before clients existed: every chatbot, phone, rule, intent and contact
    without a clientId is assigned to the operator's client. Until this runs those chatbots answer 404, on the
    webhook too.

    It only reports what it would do unless it is called with --apply, and running it twice changes nothing.

        python -m migrations.assign_operator_client            # report
        python -m migrations.assign_operator_client --apply    # write
"""
import sys

from classes import ChatBot, ChatbotPhone, Contact, Intent, Rule
from repository import operator_client

COLLECTIONS = (ChatBot, ChatbotPhone, Rule, Intent, Contact)


def orphans(document):
    return document.objects(clientId=None)


def run(apply: bool) -> dict:
    pending = {document.__name__: orphans(document).count() for document in COLLECTIONS}
    if apply and any(pending.values()):
        client_id = operator_client().uuid
        for document in COLLECTIONS:
            orphans(document).update(set__clientId=client_id)
    return pending


if __name__ == "__main__":
    apply = "--apply" in sys.argv[1:]
    for name, count in run(apply).items():
        print(f"{name}: {count} without a client{' -> assigned to the operator' if apply and count else ''}")
    if not apply:
        print("Nothing was written. Run again with --apply to assign them.")
