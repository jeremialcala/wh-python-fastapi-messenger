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

# Ejecutar como usuario no-root (seguridad). Necesita escribir application.log
# en el directorio de trabajo, por eso se le asigna la propiedad.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /usr/src/app
USER appuser

CMD ["python", "main.py"]
