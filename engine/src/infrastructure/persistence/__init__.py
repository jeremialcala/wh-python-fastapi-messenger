"""
    Persistencia: generación dinámica de modelos ORM/DTO desde JSON Schema.
"""
from .model import (
    generate_properties,
    create_dynamic_orm_model,
    create_dynamic_dto_model,
    resource_from_model,
    validate_criteria,
)

__all__ = [
    "generate_properties",
    "create_dynamic_orm_model",
    "create_dynamic_dto_model",
    "resource_from_model",
    "validate_criteria",
]
