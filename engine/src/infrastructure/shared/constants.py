# -*- coding: utf-8 -*-
"""
    Constantes transversales de infraestructura.
"""
# --- Mensajes de log ---
STARTING_AT = "Starting: %s"
ENDING_AT = "Ending: %s"
OPERATION_DATA = "operation: %s messageId: %s"

# --- Auditoría del pipeline (SOC2) ---
AUDIT_RECIBIDO = "audit: mensaje recibido origen=%s mensaje_id=%s remitente=%s"
AUDIT_BLOQUEADO = "audit: mensaje bloqueado por guardrails mensaje_id=%s motivo=%s"
AUDIT_INTENCION = "audit: intencion detectada mensaje_id=%s etiqueta=%s tipo=%s confianza=%.2f"
AUDIT_PUBLICADO = "audit: resultado publicado mensaje_id=%s tipo=%s"

# --- Base de datos (JWK) ---
KEYS = "keys"

# --- Nombres de tipos de campo (mongoengine) ---
STRING_FIELD: str = "StringField"
UUID_FIELD: str = "UUIDField"
OBJECT_ID_FIELD: str = "ObjectIdField"
EMAIL_FIELD: str = "EmailField"
DATE_TIME_FIELD: str = "DateTimeField"
INT_FIELD: str = "IntField"
IMAGE_FIELD: str = "ImageField"
ENUM_FIELD: str = "EnumField"
