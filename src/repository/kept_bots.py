# -*- coding: utf-8 -*-
"""
    The chatbots the webhook has just found, kept in memory for a moment. Every notification of a chatbot would
    otherwise go to the database for it first, and a round trip to Atlas costs about 60 ms of the 250 Meta allows.
"""
import time
from uuid import UUID

# Short: a chatbot deleted or given new credentials can still be answered as it was for this long, in a process
# that did not make the change or by a request that had already found it. Its client's open data key already
# outlives it in those processes (data_keys.OPEN_FOR).
KEEP_FOR = 30
# Only chatbots that exist get in, but nothing bounds how many a client registers.
MAX_KEPT = 1024

_kept = {}


def kept(bot_uuid: UUID):
    """The chatbot, if it was found less than KEEP_FOR seconds ago; otherwise None."""
    entry = _kept.get(bot_uuid)
    if entry is None:
        return None
    if entry[1] <= time.monotonic():
        _kept.pop(bot_uuid, None)
        return None
    return entry[0]


def keep(bot) -> None:
    if len(_kept) >= MAX_KEPT:
        now = time.monotonic()
        for bot_uuid in [key for key, (_, until) in _kept.items() if until <= now]:
            del _kept[bot_uuid]
    if len(_kept) >= MAX_KEPT:
        # The one found longest ago goes: dictionaries keep the order they were filled in.
        _kept.pop(next(iter(_kept)), None)
    _kept[bot.uuid] = (bot, time.monotonic() + KEEP_FOR)


def forget(bot_uuid: UUID | None = None) -> None:
    """Drops a chatbot from memory, or all of them. Only this process: the others wait out KEEP_FOR."""
    if bot_uuid is None:
        _kept.clear()
    else:
        _kept.pop(bot_uuid, None)
