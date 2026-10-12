# -*- coding: utf-8 -*-
import logging

from pydantic import BaseModel, Field

from .tool_settings import Settings

settings = Settings()
log = logging.getLogger(settings.environment)


class ActionParameterRequest(BaseModel):
    name: str = Field(examples=["order_id"])
    type: str = Field(default="string", examples=["string", "number", "integer", "boolean"])
    description: str = Field(default="", examples=["The unique identifier of the order"])
    required: bool = Field(default=False)
    enum: list = Field(default=[])


class ApiCallRequest(BaseModel):
    method: str = Field(default="GET", examples=["GET", "POST", "PUT", "PATCH", "DELETE"])
    url: str = Field(examples=["https://api.example.com/orders/{order_id}"])
    headers: dict = Field(default={})
    query: dict = Field(default={})
    body: dict = Field(default={})
    authType: str = Field(default="none", examples=["none", "bearer", "api_key", "basic"])
    authRef: str = Field(default="", examples=["example_api_token"])
    timeout: int = Field(default=30)


class ActionRequest(BaseModel):
    name: str = Field(examples=["get_order"])
    description: str = Field(examples=["Fetch the status and details of a customer order"])
    type: str = Field(default="api_call", examples=["api_call", "handoff"])
    parameters: list[ActionParameterRequest] = Field(default=[
        ActionParameterRequest(name="order_id", type="string",
                               description="The unique identifier of the order", required=True)
    ])
    apiCall: ApiCallRequest = Field(default=ApiCallRequest(
        method="GET", url="https://api.example.com/orders/{order_id}"))


class IntentRequest(BaseModel):
    name: str = Field(examples=["check_order_status"])
    description: str = Field(examples=["The user wants to know the status of an existing order"])
    samplePhrases: list = Field(default=[
        "Where is my order?",
        "What's the status of order 12345?",
        "Has my package shipped yet?"
    ])
    actions: list[ActionRequest] = Field(default=[ActionRequest(
        name="get_order",
        description="Fetch the status and details of a customer order"
    )])
