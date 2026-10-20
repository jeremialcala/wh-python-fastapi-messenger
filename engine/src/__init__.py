"""
    El motor de respuestas: seis workers sobre Bifröst, de una misma imagen (ADR-0008).

        - domain:          el sobre que se pasan los workers y los puertos (interfaces).
        - infrastructure:  las implementaciones concretas: Claude y el saneado de la entrada.
        - workers:         el punto de entrada de cada worker y el bucle que comparten.
"""
