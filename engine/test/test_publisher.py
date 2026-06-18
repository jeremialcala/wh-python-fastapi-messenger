# -*- coding: utf-8 -*-
"""
    Pruebas del publicador AMQP (pika mockeado).
"""
from unittest.mock import patch, MagicMock

import pika

from src.domain.enums import Origen, TipoRespuesta
from src.domain.models import ResultadoClasificado
from src.infrastructure.amqp import AmqpPublisher, send_message_to_queue


def test_send_message_to_queue_publica():
    """send_message_to_queue declara la cola y publica el cuerpo."""
    params = pika.ConnectionParameters("localhost")
    with patch("pika.BlockingConnection") as mock_conn:
        channel = MagicMock()
        mock_conn.return_value.channel.return_value = channel

        send_message_to_queue("q", "rk", "payload", params, exchange="ex")

        mock_conn.assert_called_once_with(params)
        channel.queue_declare.assert_called_once_with(queue="q")
        channel.basic_publish.assert_called_once_with(
            exchange="ex", routing_key="rk", body="payload")
        mock_conn.return_value.close.assert_called_once()


def test_amqp_publisher_serializa_resultado():
    """AmqpPublisher publica el ResultadoClasificado como JSON."""
    resultado = ResultadoClasificado(
        mensaje_id="m1", origen=Origen.WHATSAPP, remitente="u1",
        tipo_respuesta=TipoRespuesta.TEXTO)
    with patch("pika.BlockingConnection") as mock_conn:
        channel = MagicMock()
        mock_conn.return_value.channel.return_value = channel

        AmqpPublisher(queue="out", routing_key="out.rk",
                      connection_parameters=pika.ConnectionParameters("localhost")
                      ).publicar(resultado)

        _, kwargs = channel.basic_publish.call_args
        assert kwargs["routing_key"] == "out.rk"
        assert '"mensaje_id":"m1"' in kwargs["body"].replace(" ", "")
        mock_conn.return_value.close.assert_called_once()
