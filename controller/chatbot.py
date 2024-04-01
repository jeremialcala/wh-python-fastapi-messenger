# -*- coding: utf8 -*-
import logging
from uuid import uuid4, UUID

from fastapi import Response, status
from mongoengine.errors import OperationError

from classes import ChatbotRequest, ChatBot, ChatbotPhone
from classes import Settings, ResponseData, ChatbotPhoneRequest
from constants import APPLICATION_JSON, CONTENT_TYPE, CONTENT_LENGTH
from enums import Status
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
        _chatbot.uuid = uuid4()
        _chatbot.generate_verify_token()
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


async def ctr_add_phone_chatbot(bot_uuid, req: ChatbotPhoneRequest):
    log.info(f"Adding whatsapp data to this chatbot: {bot_uuid}")
    body = ResponseData(code=status.HTTP_400_BAD_REQUEST, message="BAD REQUEST", data=None)

    response = Response(
        content=body.json(),
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )
    try:
        log.debug(req.json())
        _chatbot_phone = await ChatbotPhone().generate_chatbot_phone_from_request(req=req)
        _chatbot_phone.uuid = uuid4()
        _chatbot_phone.bot_id = UUID(bot_uuid)
        _chatbot_phone.status = Status.ACT.value
        _chatbot_phone.save()
        body = ResponseData(code=status.HTTP_200_OK, message="Process completed successfully",
                            data=None)
    except Exception as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"INTERNAL SERVER ERROR",
                            data=e.__dict__)
    finally:
        response.status_code = body.code
        response.body = body.json(exclude_none=True)
        response.headers[CONTENT_LENGTH] = str(len(response.body))
        response.headers[CONTENT_TYPE] = APPLICATION_JSON

        log.info(f"this is the end, the response go with code:{response.status_code}")
        return response


async def ctr_get_chatbot_phones(bot_uuid: str, phone_uuid: str | None):
    log.info(f"Adding whatsapp data to this chatbot: {bot_uuid}")
    body = ResponseData(code=status.HTTP_400_BAD_REQUEST, message="BAD REQUEST", data=None)

    response = Response(
        content=body.json(),
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={CONTENT_TYPE: APPLICATION_JSON}
    )
    try:
        match phone_uuid:
            case None:
                _phones = [phone.get_phones_info() for phone in ChatbotPhone.objects(bot_id=UUID(bot_uuid))]
            case _:
                _phones = [phone.get_phones_info() for phone in ChatbotPhone.objects(uuid=UUID(phone_uuid))][-1]

        body = ResponseData(code=status.HTTP_200_OK, message="Process completed successfully",
                            data=_phones)
    except ValueError as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_404_NOT_FOUND, message=f"RECORD NOT FOUND")

    except Exception as e:
        log.error(e.__str__())
        body = ResponseData(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"INTERNAL SERVER ERROR",
                            data=e.__str__())
    finally:
        response.status_code = body.code
        response.body = body.json(exclude_none=True)
        response.headers[CONTENT_LENGTH] = str(len(response.body))
        response.headers[CONTENT_TYPE] = APPLICATION_JSON

        log.info(f"this is the end, the response go with code:{response.status_code}")
        return response
