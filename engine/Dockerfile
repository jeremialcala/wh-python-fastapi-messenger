FROM python:3.12
LABEL authors="Jeremi"
RUN mkdir /usr/src/app
RUN mkdir /usr/src/app/certs
WORKDIR /usr/src/app

RUN apt-get update
RUN apt-get install -y build-essential curl gcc libssl-dev libffi-dev
RUN apt-get install -y python3-dev python3-pip
RUN apt-get update
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages
COPY . ./

# Ejecutar como usuario no-root (seguridad). El código fuente queda de solo
# lectura (propiedad de root); solo el directorio de logs es escribible por el
# usuario de runtime, que es lo único que la app necesita escribir.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /usr/src/app/logs \
    && chown -R appuser:appuser /usr/src/app/logs
USER appuser

CMD ["python", "main.py"]
