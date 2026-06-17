"""
    Puertos (interfaces) del dominio. La capa de aplicación depende de estas
    abstracciones; la infraestructura las implementa.
"""
from .webhook_parser import WebhookParser
from .guardrails_policy import GuardrailsPolicy
from .intent_engine import IntentEngine
from .message_publisher import MessagePublisher

__all__ = ["WebhookParser", "GuardrailsPolicy", "IntentEngine", "MessagePublisher"]
