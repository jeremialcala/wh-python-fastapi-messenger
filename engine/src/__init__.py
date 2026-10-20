"""
    ms-python-metamsghandler — Microservicio de procesamiento de mensajería Meta.

    Estructura Clean Architecture:
        - domain:          modelos puros, enums y puertos (interfaces).
        - application:      casos de uso que orquestan el pipeline.
        - infrastructure:   implementaciones concretas (AMQP, LLM, Guardrails, etc.).
        - presentation:     puntos de entrada y cableado de dependencias.
"""
