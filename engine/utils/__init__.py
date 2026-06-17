"""
    This module have utilities methods for this project
"""
from .logging import configure_logging
from .general import documenting_parameter
from .model import (generate_properties, create_dynamic_orm_model,
                    create_dynamic_dto_model, resource_from_model)
