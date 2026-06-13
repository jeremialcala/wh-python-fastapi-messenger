# -*- coding: utf-8 -*-
import json
from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, Field
from .dto_chatbot import ChatbotRequest


class ResponseData(BaseModel):
    code: int = Field(default=200, examples=[201, 204, 400, 401, 403])
    message: str = Field(default="PROCESS COMPLETED SUCCESSFULLY")
    data: dict | list | object | None = None
    timestamp: datetime = datetime.now()


class BotResponse(BaseModel):
    code: int = Field(default=200, examples=[201, 204, 400, 401, 403])
    message: str = Field(default="PROCESS COMPLETED SUCCESSFULLY")
    data: dict | list | object | None = Field(default=ChatbotRequest())
    timestamp: datetime = datetime.now()
