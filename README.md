# SINOPAC MQ SRV

[![pipeline status](https://gitlab.tocraw.com/root/sinopac_mq_srv/badges/main/pipeline.svg)](https://gitlab.tocraw.com/root/sinopac_mq_srv/-/commits/main)
[![Maintained](https://img.shields.io/badge/Maintained-yes-green)](https://gitlab.tocraw.com/root/sinopac_mq_srv)
[![Python](https://img.shields.io/badge/Python-3.7.12-yellow?logo=python&logoColor=yellow)](https://python.org)
[![OS](https://img.shields.io/badge/OS-Linux-orange?logo=linux&logoColor=orange)](https://www.linux.org/)
[![Container](https://img.shields.io/badge/Container-Docker-blue?logo=docker&logoColor=blue)](https://www.docker.com/)

## Features

### Transfer Sinopac Python API into Restful API

- [API Docs](http://sinopac-mq-srv.tocraw.com:13333/apidocs)

### Initialize

```sh
pip install --no-warn-script-location --no-cache-dir -U -r requirements.txt
mypy --install-types --non-interactive ./src/main.py
```

### Reset all dependency

```sh
pip freeze > requirements.txt && \
pip uninstall -y -r requirements.txt
```

```sh
pip install -U \
    --no-warn-script-location \
    --no-cache-dir \
    requests shioaji Flask flasgger waitress \
    autopep8 protobuf mypy types-protobuf mypy-protobuf \
    pylint pylint-protobuf simplejson paho-mqtt && \
mypy --install-types --non-interactive ./src/main.py && \
pip freeze > requirements.txt
```

- install protoc

```sh
version=3.20.0
version=3.20.1
rm -rf /utils
mkdir /utils
cd /utils
curl -fSL https://github.com/protocolbuffers/protobuf/releases/download/v$version/protoc-$version-linux-x86_64.zip --output protobuf.zip
unzip protobuf.zip -d protobuf
cd /sinopac_mq_srv
```

### Git

```sh
git fetch --prune --prune-tags origin
git check-ignore *
```

## Authors

- [**Tim Hsu**](https://gitlab.tocraw.com/root)
