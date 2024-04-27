FROM ubuntu:latest
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

CMD ["uvicorn", "app:app","--host", "0.0.0.0", "--port", "5002", "--workers", "4"]
EXPOSE 5002