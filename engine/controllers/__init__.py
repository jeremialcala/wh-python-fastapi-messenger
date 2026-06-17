"""
    This module handles the AMQP protocol, and the entities this service.
"""
from .messages import process_messages
from .amqp import (send_message_to_queue, ack_message, execute_operation,
                   on_message, get_amqp_connection_parameters)
from .security import retrieve_key, encrypt_data, decrypt_data
