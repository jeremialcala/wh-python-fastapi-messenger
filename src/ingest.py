# -*- coding: utf-8 -*-
"""
    The ingestion worker (ADR-0021): reads the notifications the webhook published on WEBHOOK, with Bifröst's durable
    consumer `ingesta`, and ingests them one by one, in order (controller/ingestion.py). It serves no route.

        python ingest.py

    Each event is acknowledged once all its messages are ingested. One that has to wait (the database, Andvari,
    Bifröst or Hermod are not there) is not acknowledged: Bifröst delivers it again after the consumer's backoff,
    30 s, 1 min, 5 min... for as long as the stream keeps it, 7 days. One that can never be ingested is dropped.

    It is alive while it touches ALIVE_FILE: the container's health check looks at how old that file is.
"""
import asyncio
import json
import logging
import pathlib
import signal
import ssl

import nats
import nats.errors

import bus
import service  # Settings, logging, the key service and the publisher of this process.
from controller.ingestion import RETRY_LATER, Unprocessable, ingest_notification
from utils import configure_logging, describe

settings = service.settings
log = logging.getLogger(settings.environment)

STREAM, CONSUMER = "WEBHOOK", "ingesta"
BATCH = 10           # events asked for at a time: they are still ingested one after the other
WAIT = 5             # seconds a request for events waits when there are none
ALIVE_FILE = pathlib.Path("/tmp/ingest-alive")


async def handle(message) -> str:
    """What is done with one event: acknowledged, dropped, or left for Bifröst to deliver again."""
    try:
        event = json.loads(message.data)
    except (ValueError, UnicodeDecodeError):
        log.error("An event of WEBHOOK is not JSON: dropped")
        await message.term()
        return "dropped"
    trace = (message.headers or {}).get("traceparent")
    try:
        outcome = await ingest_notification(event, trace)
    except Unprocessable as e:
        log.warning(f"An event of WEBHOOK cannot be ingested, dropped: {e}")
        await message.term()
        return "dropped"
    except RETRY_LATER as e:
        log.error(f"An event of WEBHOOK has to wait: {type(e).__name__}")
        return "waiting"
    except Exception as e:
        # Not known to be of the event: it is tried again rather than lost.
        log.error(f"An event of WEBHOOK could not be ingested: {describe(e)}")
        return "waiting"
    await message.ack()
    log.info(f"Event of WEBHOOK ingested: {outcome}")
    return "acknowledged"


async def consume(subscription, stop: asyncio.Event) -> None:
    while not stop.is_set():
        ALIVE_FILE.touch()
        try:
            messages = await subscription.fetch(BATCH, timeout=WAIT)
        except nats.errors.TimeoutError:
            continue
        except nats.errors.Error as e:
            # The connection is reconnecting, or Bifröst is restarting: the client recovers on its own.
            log.warning(f"Waiting for {STREAM}: {type(e).__name__}")
            await asyncio.sleep(1)
            continue
        for message in messages:
            await handle(message)


async def subscribe(url: str, user: str | None, password: str | None, ca: str | None, inbox_prefix: str | None):
    """
        The consumer is Bifröst's, made when it was provisioned: it is bound, never created here, and the worker's
        user may not create one.
    """
    tls = None
    if url.startswith("tls://"):
        tls = ssl.create_default_context(cafile=ca or None)
    connection = await nats.connect(url, user=user, password=password, tls=tls, name="ingest",
                                    inbox_prefix=inbox_prefix or "_INBOX", max_reconnect_attempts=-1)
    return connection, await connection.jetstream().pull_subscribe_bind(durable=CONSUMER, stream=STREAM)


async def main() -> None:
    configure_logging()
    if not settings.nats_url:
        raise SystemExit("The ingestion worker needs NATS_URL")
    stop = asyncio.Event()
    for name in ("SIGTERM", "SIGINT"):
        if hasattr(signal, name):
            try:
                asyncio.get_running_loop().add_signal_handler(getattr(signal, name), stop.set)
            except NotImplementedError:
                pass
    connection, subscription = await subscribe(settings.nats_url, settings.nats_user, settings.nats_password,
                                               settings.nats_ca, settings.nats_inbox_prefix)
    log.info(f"Ingesting {STREAM} with the consumer {CONSUMER}")
    try:
        await consume(subscription, stop)
    finally:
        await connection.drain()
        await bus.close()


if __name__ == "__main__":
    asyncio.run(main())
