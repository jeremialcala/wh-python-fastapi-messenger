# -*- coding: utf-8 -*-
"""
    The register of what was deleted. A backup of the database is kept for a year, and restoring one brings back
    whatever was deleted after it was taken: this is what says which deletions to make again (ADR-0014).

    It lives outside the database, in files, because a restore would take it back in time with everything else.
    It holds identifiers made up by the service and dates: no name, no number, nothing of what was deleted.

    Every deletion is written here before it is made. If it cannot be written, nothing is deleted.
"""
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

CONTACT, CHATBOT, CLIENT = "contact", "chatbot", "client"

# One file per month, so that what is too old to matter goes a whole file at a time.
FILE = re.compile(r"^erasures-(\d{4})-(\d{2})\.jsonl$")
# How long an entry is kept: the 365 days a backup lives, and a margin. No backup older than that is left to
# bring anything back.
KEEP_MONTHS = 14

_directory = None
# Between threads of one process. Between processes it is the append itself that keeps the lines apart: that
# holds on Linux, where the service runs, and not on Windows, where several workers at once can lose a line.
_writing = threading.Lock()


class RegisterUnavailable(Exception):
    """The register cannot be written or read. Nothing is deleted until it can: the caller answers 503."""


def configure(directory) -> None:
    """Sets where the register is kept. Done once, when the application starts."""
    global _directory
    _directory = Path(directory) if directory else None


def _month(moment: datetime) -> int:
    return moment.year * 12 + moment.month - 1


def _files() -> list:
    """The files of the register, oldest first, each with the month it holds."""
    if _directory is None:
        raise RegisterUnavailable("not configured")
    try:
        names = sorted(name for name in os.listdir(_directory) if FILE.match(name))
    except FileNotFoundError:
        return []
    except OSError as e:
        raise RegisterUnavailable(type(e).__name__) from None
    return [(_directory / name, int(FILE.match(name).group(1)) * 12 + int(FILE.match(name).group(2)) - 1)
            for name in names]


def record(kind: str, client_id: UUID, bot_id: UUID | None = None, contacts=()) -> None:
    """Writes down a deletion that is about to be made, and only returns once it is on disk."""
    now = datetime.now(timezone.utc)
    entry = {"at": now.isoformat(timespec="seconds"), "kind": kind, "clientId": str(client_id)}
    if bot_id is not None:
        entry["botId"] = str(bot_id)
    if contacts:
        entry["contacts"] = [str(contact) for contact in contacts]
    line = (json.dumps(entry, separators=(",", ":")) + "\n").encode()
    try:
        with _writing:
            for path, month in _files():
                if month <= _month(now) - KEEP_MONTHS:
                    path.unlink()
            _directory.mkdir(parents=True, exist_ok=True)
            # Appended in a single write: two processes writing at once do not mix their lines.
            descriptor = os.open(_directory / f"erasures-{now:%Y-%m}.jsonl",
                                 os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(descriptor, line)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except OSError as e:
        # Only the kind of failure: the text carries the path.
        raise RegisterUnavailable(type(e).__name__) from None


def entries() -> tuple:
    """
        Everything in the register, oldest first, and how many lines could not be read. A register that is not
        there is not an empty one: it is read after restoring a backup, and reading it from the wrong place would
        say there is nothing to delete again.
    """
    if _directory is not None and not _directory.is_dir():
        raise RegisterUnavailable("not found")
    read, unreadable = [], 0
    for path, _ in _files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise RegisterUnavailable(type(e).__name__) from None
        for line in lines:
            try:
                entry = json.loads(line)
                read.append({"at": entry["at"], "kind": entry["kind"], "clientId": UUID(entry["clientId"]),
                             "botId": UUID(entry["botId"]) if "botId" in entry else None,
                             "contacts": [UUID(contact) for contact in entry.get("contacts", [])]})
            except (ValueError, KeyError, TypeError):
                # A line cut short: the process died while writing it, before it deleted anything.
                unreadable += 1
    return read, unreadable
