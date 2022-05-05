FROM python:3.7.13-bullseye
USER root

ENV TZ=Asia/Taipei
ENV DEPLOYMENT=docker

ARG PYPORT
ARG TRADEID
ARG TRADEPASS
ARG CAPASS

WORKDIR /
RUN mkdir sinopac_mq_srv
WORKDIR /sinopac_mq_srv
COPY . .

RUN apt update -y && \
    apt install -y tzdata && \
    apt autoremove -y && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-warn-script-location --no-cache-dir -r requirements.txt

ENTRYPOINT ["/sinopac_mq_srv/scripts/docker-entrypoint.sh"]
