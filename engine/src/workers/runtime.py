# -*- coding: utf-8 -*-
"""
    Lo que tienen en común los workers del motor (ADR-0008): se atan a su consumidor de Bifröst, leen un mensaje
    tras otro, publican lo que sigue y solo entonces confirman. Como la ingesta del gateway (src/ingest.py):

        * **confirmado**: hecho y publicado lo siguiente;
        * **descartado**: un mensaje que nunca se podrá atender (no es JSON, no cumple el contrato). Se termina y el
          log dice por qué, nunca qué traía;
        * **en espera**: algo que hace falta no está (Bifröst, Claude). No se confirma, y Bifröst lo entrega otra vez
          tras la espera del consumidor, hasta su `max_deliver`. Al agotarlos, el aviso de Bifröst lo deja a la vista.

    El consumidor es de Bifröst, creado al aprovisionarlo: el worker se ata a él y su usuario no puede crear otro.
    Mientras vive toca un fichero, y la comprobación de salud del contenedor mira su edad.
"""
import asyncio
import enum
import logging
import pathlib
import signal
import ssl
import sys
from typing import Awaitable, Callable

import nats
import nats.errors

from shared import tracing
from shared.bus.nats_jetstream import NatsPublisher
from src.workers.settings import WorkerSettings

log = logging.getLogger(__name__)

LOTE = 1      # mensajes pedidos cada vez: el consumidor tiene uno solo en vuelo (max_ack_pending 1)
ESPERA = 5    # segundos que espera cada petición cuando no hay mensajes


class Resultado(enum.Enum):
    """Lo que se hizo con un mensaje. Los valores son los de `gateway.outcome` en las trazas."""
    CONFIRMADO = "acknowledged"
    DESCARTADO = "dropped"
    EN_ESPERA = "waiting"


Atender = Callable[[object], Awaitable[Resultado]]


def entregas(mensaje) -> int:
    """Cuántas veces ha entregado Bifröst este mensaje, contando esta."""
    metadata = getattr(mensaje, "metadata", None)
    return getattr(metadata, "num_delivered", 1) or 1


async def resolver(mensaje, atender: Atender) -> Resultado:
    """Atiende un mensaje y hace con él lo que diga el resultado. Un fallo no previsto lo deja en espera."""
    try:
        resultado = await atender(mensaje)
    except Exception as e:  # pylint: disable=broad-except
        # No se sabe si es del mensaje: se intenta otra vez antes que perderlo.
        log.error("Un mensaje no se pudo atender: %s", type(e).__name__)
        return Resultado.EN_ESPERA
    if resultado is Resultado.CONFIRMADO:
        await mensaje.ack()
    elif resultado is Resultado.DESCARTADO:
        await mensaje.term()
    return resultado


async def consumir(subscription, stop: asyncio.Event, atender: Atender, vivo: pathlib.Path) -> None:
    """Lee y atiende un mensaje tras otro hasta `stop`, tocando `vivo` en cada vuelta."""
    while not stop.is_set():
        vivo.touch()
        try:
            mensajes = await subscription.fetch(LOTE, timeout=ESPERA)
        except asyncio.TimeoutError:
            # Nada que leer en ESPERA segundos. nats-py lo dice con su TimeoutError o con el de asyncio (la lección
            # de la ingesta del gateway, PR #60): los dos son este.
            continue
        except nats.errors.Error as e:
            # Reconectando, o Bifröst reiniciándose: el cliente se recupera solo.
            log.warning("Esperando a Bifröst: %s", type(e).__name__)
            await asyncio.sleep(1)
            continue
        for mensaje in mensajes:
            await resolver(mensaje, atender)


async def conectar(settings: WorkerSettings, nombre: str):
    """La conexión con la que el worker lee de su consumidor. Se reconecta sola, para siempre."""
    tls = ssl.create_default_context(cafile=settings.nats_ca or None) if settings.nats_url.startswith("tls://") \
        else None
    return await nats.connect(settings.nats_url, user=settings.nats_user, password=settings.nats_password, tls=tls,
                              name=nombre, inbox_prefix=settings.nats_inbox_prefix, max_reconnect_attempts=-1)


def publicador(settings: WorkerSettings, nombre: str) -> NatsPublisher:
    """El publicador de `shared`, con el usuario del worker: espera el acuse y deduplica por Nats-Msg-Id."""
    return NatsPublisher(settings.nats_url, settings.nats_user, settings.nats_password, settings.nats_ca,
                         settings.nats_inbox_prefix, name=nombre)


def configurar_log(nivel: str) -> None:
    """Al stdout del contenedor, que es de donde lo recoge el despliegue."""
    logging.basicConfig(stream=sys.stdout, level=nivel.upper(),
                        format="[%(asctime)s] %(levelname)-7s [%(name)s] %(message)s")


async def ejecutar(nombre: str, settings: WorkerSettings, stream: str, consumidor: str,
                   crear: Callable[[int], Awaitable[tuple[Atender, Callable[[], Awaitable[None]]]]]) -> None:
    """
        El bucle de un worker hasta que le piden parar. `crear` recibe el `max_deliver` del consumidor y devuelve
        cómo atender cada mensaje y cómo cerrar lo que abrió.
    """
    configurar_log(settings.log_level)
    tracing.configure(f"engine-{nombre}")
    stop = asyncio.Event()
    for senal in ("SIGTERM", "SIGINT"):
        if hasattr(signal, senal):
            try:
                asyncio.get_running_loop().add_signal_handler(getattr(signal, senal), stop.set)
            except NotImplementedError:
                # Windows no tiene manejadores de señales en el bucle: allí Ctrl+C para el worker tal cual.
                pass
    connection = await conectar(settings, nombre)
    cerrar = None
    try:
        subscription = await connection.jetstream().pull_subscribe_bind(durable=consumidor, stream=stream)
        info = await subscription.consumer_info()
        atender, cerrar = await crear(info.config.max_deliver or -1)
        log.info("%s lee %s con el consumidor %s", nombre, stream, consumidor)
        await consumir(subscription, stop, atender, pathlib.Path(f"/tmp/{nombre}-alive"))
    finally:
        if cerrar is not None:
            await cerrar()
        await connection.drain()
        tracing.shutdown()
