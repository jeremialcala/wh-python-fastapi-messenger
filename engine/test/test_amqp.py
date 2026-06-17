"""
    This class test controllers/amqp.py
"""
from unittest.mock import patch, MagicMock
import json
import pytest
import pika
from controllers import (send_message_to_queue, ack_message, execute_operation)
from classes import Settings

_set = Settings()


@pytest.fixture(name="connection_parameters")
def fixture_connection_parameters():
    """
        this is a mock connection for AMQP tests
    :return:
    """
    return pika.ConnectionParameters("localhost")


def test_get_amqp_connection_parameters():
    """
        Testing the connection parameters methods
    """

    with patch("pika.BlockingConnection") as mock_connection:
        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel


def test_execute_operation():
    """
        This method test the execute operation controller/
    """

    with patch("pika.BlockingConnection") as mock_connection:
        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel
        execute_operation(
           mock_connection,
           mock_connection.channel(),
           {},
            0,
            json.dumps(
                {
                    "client_id": "971ad8f0-362b-11ef-8905-9b6d06b6f8cd",
                    "resource": "user",
                    "operation": "POST",
                    "messageId": "dbc09d10-68ca-11ef-b1cd-afa401cd546c",
                    "destination": "dd68ebb8-68ca-11ef-a63e-13d0432d05b8",
                    "origen": "a49c75ce-362b-11ef-9ae4-97debd42cf94",
                    "body": "eyJmaXJzdE5hbWUiOiAiVGltb3RoeSIsICJtaWRkbGVOYW1lIjogIkxhdXJlbiIsI"
                            "CJsYXN0TmFtZSI6ICJFc3BhcnphIiwgImVtYWlsQWRkcmVzcyI6ICJ0ZXNwYXJ6YUB"
                            "nbWFpbC5jb20iLCAicGhvbmVOdW1iZXIiOiAiMDAxLTQ3Ni00NTQtMTIyNng0MjA0In0="
                }).encode("utf-8")
            )


def test_settings():
    """

    :return:
    """
    assert _set.queue_name == "users"


def test_ack_message():
    """
        This method test the ack_messages from controllers/

    """
    with patch("pika.BlockingConnection") as mock_connection:
        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel

        ack_message(mock_channel, delivery_tag=0)


def test_send_message_to_queue(connection_parameters):
    """
        This method test the send_message_to_queue from controllers/
    """
    with patch("pika.BlockingConnection") as mock_connection:
        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel

        send_message_to_queue("test_queue", _set.amqp_routing_key,
                              "test_message", connection_parameters)

        mock_connection.assert_called_once_with(connection_parameters)
        mock_channel.queue_declare.assert_called_once_with(queue="test_queue")
        mock_channel.basic_publish.assert_called_once_with(
            exchange=_set.amqp_exchange,
            routing_key=_set.amqp_routing_key,
            body="test_message",
        )
