# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from uuid import uuid4, UUID
from inspect import currentframe
from mongoengine import *

from enums import Status
from .tool_settings import Settings

settings = Settings()
log = logging.getLogger(settings.environment)
connect(
    db=settings.db_name,
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host
)


class ActionParameter(EmbeddedDocument):
    """
    A single JSON-Schema style input parameter that an action needs from the user.
    """
    name = StringField(required=True)
    type = StringField(default="string")  # string | number | integer | boolean | object | array
    description = StringField()
    required = BooleanField(default=False)
    enum = ListField(StringField())


class ApiCall(EmbeddedDocument):
    """
    HTTP request template for an action. This service only stores it; the
    downstream worker resolves the placeholders and performs the request.
    """
    method = StringField(default="GET")  # GET | POST | PUT | PATCH | DELETE
    url = StringField(required=True)  # template with {param} placeholders
    headers = DictField()
    query = DictField()
    body = DictField()
    authType = StringField(default="none")  # none | bearer | api_key | basic
    authRef = StringField()  # name/reference of the secret, NEVER the secret itself
    timeout = IntField(default=30)


class Action(EmbeddedDocument):
    """
    Something the bot can do for an intent, typically an API call. Modeled to
    map cleanly onto an LLM tool definition via ``to_tool_schema``.
    """
    name = StringField(required=True)
    description = StringField(required=True)
    type = StringField(default="api_call")  # api_call | handoff | ...
    parameters = ListField(EmbeddedDocumentField(ActionParameter))
    apiCall = EmbeddedDocumentField(ApiCall)
    status = IntField(default=Status.ACT.value)

    def to_tool_schema(self) -> dict:
        """
        Emit an Anthropic/OpenAI-compatible tool definition built from this
        action's parameters, so the worker can hand it straight to the model.
        """
        properties = {}
        required = []
        for param in self.parameters:
            schema = {"type": param.type}
            if param.description:
                schema["description"] = param.description
            if param.enum:
                schema["enum"] = list(param.enum)
            properties[param.name] = schema
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


class Intent(Document):
    uuid = UUIDField(required=True, unique=True, default=uuid4())
    botId = UUIDField(required=True)
    name = StringField(required=True)
    description = StringField(required=True)
    samplePhrases = ListField(StringField())
    actions = ListField(EmbeddedDocumentField(Action))
    createdAt = DateTimeField(required=True, default=datetime.now())
    status = IntField(required=True, default=Status.REG.value)
    statusDate = DateTimeField(required=True, default=datetime.now())

    def intent_info(self) -> dict:
        log.info(f"Executing: {currentframe().f_code.co_name}")
        return {
            "uuid": str(self.uuid),
            "botId": str(self.botId),
            "name": self.name,
            "description": self.description,
            "samplePhrases": list(self.samplePhrases),
            "actions": [self.action_info(action) for action in self.actions],
            "status": Status(self.status).name
        }

    @staticmethod
    def action_info(action: Action) -> dict:
        return {
            "name": action.name,
            "description": action.description,
            "type": action.type,
            "status": Status(action.status).name,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "enum": list(p.enum)
                } for p in action.parameters
            ],
            "apiCall": {
                "method": action.apiCall.method,
                "url": action.apiCall.url,
                "headers": dict(action.apiCall.headers),
                "query": dict(action.apiCall.query),
                "body": dict(action.apiCall.body),
                "authType": action.apiCall.authType,
                "authRef": action.apiCall.authRef,
                "timeout": action.apiCall.timeout
            } if action.apiCall is not None else None
        }

    def tool_definitions(self) -> list:
        """All active actions of this intent as LLM tool definitions."""
        return [action.to_tool_schema() for action in self.actions
                if action.status == Status.ACT.value]

    @staticmethod
    async def get_intents_by_bot(bot_id: str):
        log.info(f"Executing: {currentframe().f_code.co_name}")
        return [intent for intent in Intent.objects(botId=UUID(bot_id))
                if intent.status != Status.DIS.value]

    @staticmethod
    async def get_intent_by_uuid(_uuid: str):
        log.info(f"Executing: {currentframe().f_code.co_name}")
        return [intent for intent in Intent.objects(uuid=UUID(_uuid))][-1]
