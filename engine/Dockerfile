# La imagen del motor de respuestas (ADR-0023 del gateway: ghcr.io/jeremialcala/chatbot-engine). Se construye desde
# la raíz del monorepo, que es donde está `shared/`:
#
#   docker build -f engine/Dockerfile .
#
# Lo que entra en el contexto lo dice engine/Dockerfile.dockerignore, que BuildKit usa en lugar del .dockerignore
# de la raíz (ese deja fuera engine/, para la imagen del gateway).
#
# Dos etapas: nemoguardrails arrastra annoy, que se compila con C++, y los compiladores no tienen por qué quedarse en
# la imagen que corre. Las dos bases van por digest: un tag es móvil y la misma línea daría otra imagen otro día.
# Para renovarlas:  docker buildx imagetools inspect python:3.12 --format '{{.Manifest.Digest}}'
#                   docker buildx imagetools inspect python:3.12-slim --format '{{.Manifest.Digest}}'
FROM python:3.12@sha256:42dc0ee40d7707e2f2ee506a1cbe52e09ab11c207c5b429342638f83177601fe AS dependencias

# Solo lo de ejecución, del lock y con hashes: nada se vuelve a resolver al construir.
COPY engine/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --prefix=/instalado -r /tmp/requirements.lock

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
LABEL authors="Jeremi"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=dependencias /instalado /usr/local

WORKDIR /usr/src/app

# Solo el código: ni las pruebas, ni los docs, ni config.env, que además el .dockerignore deja fuera del contexto.
COPY engine/main.py engine/logging_config.yaml ./
COPY engine/src/ ./src/
# Y lo que comparte con el gateway, importable como `shared`.
COPY shared/ ./shared/

# Corre sin privilegios. El código queda de solo lectura (de root); el usuario solo escribe en logs/.
RUN useradd --system --uid 10001 --no-create-home appuser \
 && mkdir -p /usr/src/app/logs \
 && chown appuser /usr/src/app/logs
USER appuser

CMD ["python", "main.py"]
