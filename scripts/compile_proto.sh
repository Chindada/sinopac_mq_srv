#!/bin/bash

git clone git@gitlab.tocraw.com:root/trade_agent_protobuf.git

protoc -I=. --python_out=. --mypy_out=. ./trade_agent_protobuf/src/*.proto

mv ./trade_agent_protobuf/src/*_pb2.py ./src/protobuf
mv ./trade_agent_protobuf/src/*_pb2.pyi ./src/protobuf

rm -rf trade_agent_protobuf
