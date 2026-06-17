# -*- coding: utf-8 -*-
"""
    This controller handles the service data lifecycle.

"""
import json
import logging.config
from functools import wraps
from inspect import currentframe

from classes import Settings
from constants import STARTING_AT, ENDING_AT, OPERATION_DATA
from constants import operations
from utils import (configure_logging, create_dynamic_dto_model)

_set = Settings()
log = logging.getLogger(__name__)
logging.config.dictConfig(configure_logging())


def service_lifecycle(func):
    """
        This is a function that process messages outside the AMQP controller.
    :return: Response code with the result of this operation
    """
    log.info(STARTING_AT, currentframe().f_code.co_name)

    @wraps(func)
    def wrapper(*args, **kwargs):
        """
            This is a Wrapper is used to execute the lifecycle operations.
            With this tool we are going to make templates out of this code.

            TODO: Create the security module to deserialize a JWE message
            TODO: Separate all operation on different methods and use match to execute here

        """
        log.info(STARTING_AT, currentframe().f_code.co_name)
        dto = create_dynamic_dto_model("message", json.loads(_set.dto_message))
        message = dto(**json.loads(args[-1].decode("utf-8")))
        log.info(message.body)

        match message.operation:
            case operations.GET:
                log.info(OPERATION_DATA, message.operation, message.messageId)

            case operations.POST:
                log.info(OPERATION_DATA, message.operation, message.messageId)

            case operations.PUT:
                log.info(OPERATION_DATA, message.operation, message.messageId)

            case operations.PATCH:
                log.info(OPERATION_DATA, message.operation, message.messageId)

            case operations.DELETE:
                log.info(OPERATION_DATA, message.operation, message.messageId)

            case _:
                pass

        data = {"response_code": 200, "message": "Process OK"}
        # def execute_operation(connection, channel, header_frame, delivery_tag, body):
        rags = (args[0], args[1], args[2], args[3], data)
        log.info(ENDING_AT, currentframe().f_code.co_name)
        return func(*rags, **kwargs)

    log.info(ENDING_AT, currentframe().f_code.co_name)
    return wrapper
