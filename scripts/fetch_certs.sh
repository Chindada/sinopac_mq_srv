#!/bin/bash

git clone git@gitlab.tocraw.com:root/trade_agent_mqtt.git

rm -rf ./configs/certs

mkdir ./configs/certs

cp ./trade_agent_mqtt/configs/certs/* ./configs/certs

rm -rf trade_agent_mqtt
