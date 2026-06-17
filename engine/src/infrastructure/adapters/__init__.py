"""
    Adaptadores de webhooks de Meta (Messenger / WhatsApp / Instagram).
"""
from .messenger import MessengerParser
from .whatsapp import WhatsAppParser
from .instagram import InstagramParser
from .resolver import WebhookResolver, OrigenNoSoportado
from .sanitize import sanitizar_texto, sanitizar_id

__all__ = [
    "MessengerParser",
    "WhatsAppParser",
    "InstagramParser",
    "WebhookResolver",
    "OrigenNoSoportado",
    "sanitizar_texto",
    "sanitizar_id",
]
