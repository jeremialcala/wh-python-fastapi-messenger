# -*- coding: utf8 -*-
import logging
from uuid import uuid4

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot
from classes import Settings, ResponseData
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH

settings = Settings()
log = logging.getLogger(settings.environment)


async def ctr_create_chatbot(request: ChatbotRequest) -> Response:
    log.info(f"We are creating this chatbot {request.name}")
    body = ResponseData(code=status.HTTP_400_BAD_REQUEST, message="BAD REQUEST", data=None)

    response = Response(
        content=body.json(),
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )

    try:
        _chatbot = ChatBot.from_json(request.json())
        _chatbot.save()
        body = ResponseData(code=status.HTTP_200_OK, message="Process completed successfully",
                            data=_chatbot.chatbot_info())
    except OperationError as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_400_BAD_REQUEST, message=f"This chatbot already exists {request.name}",
                            data=None)
    except Exception as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"INTERNAL SERVER ERROR",
                            data=None)
    finally:
        response.status_code = body.code
        response.body = body.json(exclude_none=True)
        response.headers[CONTENT_LENGTH] = str(len(response.body))
        response.headers[CONTENT_TYPE] = APPLICATION_JSON

        log.info(f"this is the end, the response go with code:{response.status_code}")
        return response


async def ctr_get_chatbot_from_uuid(_uuid: str) -> Response:
    log.info(f"We are looking for this chatbot {_uuid}")
    body = ResponseData(code=status.HTTP_400_BAD_REQUEST, message="BAD REQUEST", data=None)

    response = Response(
        content=body.json(),
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )
    try:
        _chatbot = await ChatBot().get_chatbot_by_uuid(_uuid)
        body = ResponseData(code=status.HTTP_200_OK, message="Process completed successfully",
                            data=_chatbot.chatbot_info())
    except ValueError as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_404_NOT_FOUND, message=f"This chatbot {_uuid} was not found",
                            data=None)
    except Exception as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"INTERNAL SERVER ERROR",
                            data=None)
    finally:
        response.status_code = body.code
        response.body = body.json(exclude_none=True)
        response.headers[CONTENT_LENGTH] = str(len(response.body))
        response.headers[CONTENT_TYPE] = APPLICATION_JSON

        log.info(f"this is the end, the response go with code:{response.status_code}")
        return response




