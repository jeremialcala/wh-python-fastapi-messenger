# -*- coding: utf-8 -*-
"""
    This util point to create generic objects using json schema.

"""

from uuid import uuid4
from datetime import datetime
import json
from typing import Annotated
from pydantic import Field, create_model
from mongoengine import (
    Document,
    StringField,
    UUIDField,
    EmailField,
    ObjectIdField,
    DateTimeField,
    IntField,
    EnumField,
    ImageField
)

from enums import Status
import constants


TYPES = {
        'string': str,
        'array': list,
        'boolean': bool,
        'integer': int,
        'float': float,
        'number': float,
    }

FIELDS = {
    constants.STRING_FIELD: StringField,
    constants.INT_FIELD: IntField,
    constants.OBJECT_ID_FIELD: ObjectIdField,
    constants.UUID_FIELD: UUIDField,
    constants.EMAIL_FIELD: EmailField,
    constants.DATE_TIME_FIELD: DateTimeField,
    constants.IMAGE_FIELD: EmailField,
    constants.ENUM_FIELD: EnumField,
}


def generate_properties(json_schema: dict) -> dict:
    """
        Using a json file with the document schema
        return a properties for a new dynamic model

    :param json_schema: a plain dict with the schema description
    :return: a dict with all field of the dynamic model
    """
    _model = {}
    for k, v in json_schema.items():
        match v["type"]:
            case constants.UUID_FIELD:
                _model[k] = UUIDField(
                    required=v["required"],
                    unique=v["unique"],
                    default=uuid4()
                )

            case constants.STRING_FIELD:
                _model[k] = StringField(
                    required=v["required"],
                    unique=v["unique"]
                )

            case constants.EMAIL_FIELD:
                _model[k] = EmailField(
                    required=v["required"],
                    unique=v["unique"]
                )

            case constants.DATE_TIME_FIELD:
                _model[k] = DateTimeField(
                    required=v["required"],
                    unique=v["unique"],
                    default=datetime.now()
                )

            case constants.IMAGE_FIELD:
                _model[k] = ImageField(
                    required=v["required"],
                    unique=v["unique"],
                    default=datetime.now()
                )

            case _:
                pass

    _model["createdAt"] = DateTimeField(
        required=False,
        unique=False,
        default=datetime.now()
    )
    _model["status"] = EnumField(
        Status,
        required=True,
        unique=False,
        default=Status.REG
    )
    _model["statusDate"] = DateTimeField(
        required=False,
        unique=False,
        default=datetime.now()
    )

    return _model


def create_dynamic_orm_model(name: str, properties: dict) -> Document:
    """
        This method will create and return a new dynamic model
    :param name: The name of this model
    :param properties: the scheme definition for this model
    :return: The new dynamic model.
    """
    return type(name, (Document, ), properties)


def create_dynamic_dto_model(name: str, properties: dict):
    """
        this creates a dynamic dto from a json schema.
        { "name": {"type": "String", "description": "this is the description for the field"}}

    :return:
    """
    _model = {}
    for k, v in properties.items():
        _model[k] = Annotated[
            TYPES[v["type"]],
            Field(alias=k, description=v["description"])
        ]

    return create_model(name, **_model)


def resource_from_model(_model: Document, _criteria: dict):
    """

    :param _model:
    :param _criteria:
    :return:
    """
    _resource = [resource for resource in list(_model.objects())
                 if validate_criteria(_data=json.loads(resource.to_json()), _criteria=_criteria)]
    return _resource if len(_resource) > 1 else _resource[-1]


def validate_criteria(_data: dict, _criteria: dict) -> bool:
    """
        This is a search of a criteria send on a dict another dict data,
        will return True if the full criteria match.

    :param _data:
    :param _criteria:
    :return:
    """
    return all(item in (_data_item for _data_item in _data.items())
               for item in  (_criteria_item for _criteria_item in _criteria.items()))
