"""
    Claude, por la API de Anthropic, como LLM del motor (ADR-0009).
"""
from .clasificador import ClaudeClasificador
from .redactor import ClaudeRedactor

__all__ = ["ClaudeClasificador", "ClaudeRedactor"]
