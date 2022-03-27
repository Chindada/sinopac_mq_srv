#!/usr/local/bin/python
# -*- coding: utf-8 -*-
'''SINOPAC PYTHON API FORWARDER'''
import logging
import os
import random
import ssl
import string
import sys
import threading
import time
import typing
from datetime import datetime
from re import search

import paho.mqtt.client as paho
import shioaji as sj
from flasgger import Swagger
from flask import Flask, jsonify, request
from waitress import serve

import mq_topic
from protobuf import trade_agent_pb2

deployment = os.getenv('DEPLOYMENT')
server_token = ''.join(random.choice(string.ascii_letters) for _ in range(25))

api = Flask(__name__)
swagger = Swagger(api)

token = sj.Shioaji()
login_mutex = threading.Lock()
mutex = threading.Lock()
simulation_count_lock = threading.Lock()
MQTT_CLIENT = paho.Client()
MQTT_CONNECTING = False

log_format = str()
extension_name = str()

if deployment == 'docker':
    log_format = '{"time":"%(asctime)s","user":"%(name)s","level":"%(levelname)s","message":"%(message)s"}'
    extension_name = '.json'
else:
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    extension_name = '.log'

console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('./logs/'+datetime.now().strftime("%Y-%m-%dT%H%M")+extension_name)

console_handler.setFormatter(logging.Formatter(log_format))
file_handler.setFormatter(logging.Formatter(log_format))

logger = logging.getLogger()
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)


SINOPAC_LOGIN_STATUS = int()
UP_TIME = int()
ERROR_TIMES = int()


HISTORY_ORDERS: typing.List[sj.order.Trade] = []
CURRENT_STOCK_COUNT: typing.Dict[str, int] = {}
ALL_STOCK_NUM_LIST: typing.List[str] = []
BIDASK_SUB_LIST: typing.List[str] = []
QUOTE_SUB_LIST: typing.List[str] = []
FUTURE_SUB_LIST: typing.List[str] = []


@ api.route('/sinopac-mq-srv/basic/stock-detail', methods=['GET'])
def get_all_stock_detail():
    '''Get all stock detail from contracts and send to 'internal/stock_detail'
    ---
    tags:
      - Basic
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      Result:
        type: object
        properties:
          result:
            type: string
    '''
    response = trade_agent_pb2.StockDetailResponse()
    tse_001 = token.Contracts.Indexs.TSE.TSE001
    res = trade_agent_pb2.StockDetailMessage()
    res.exchange = tse_001.exchange
    res.category = tse_001.category
    res.code = tse_001.code
    res.name = tse_001.name
    res.reference = tse_001.reference
    res.update_date = tse_001.update_date
    res.day_trade = tse_001.day_trade
    response.stock.append(res)
    global ALL_STOCK_NUM_LIST  # pylint: disable=global-statement
    tmp = ALL_STOCK_NUM_LIST
    for row in tmp:
        contract = token.Contracts.Stocks[row]
        if contract is None:
            tmp.remove(row)
            logger.info('%s is no data', row)
            continue
        res = trade_agent_pb2.StockDetailMessage()
        res.exchange = contract.exchange
        res.category = contract.category
        res.code = contract.code
        res.name = contract.name
        res.reference = contract.reference
        res.update_date = contract.update_date
        res.day_trade = contract.day_trade
        response.stock.append(res)
    ALL_STOCK_NUM_LIST = tmp
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_stock_detail, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/real-time/all-snapshot', methods=['GET'])
def get_all_snapshot():
    '''Get all stock latest snapshot and send to 'internal/snapshot_all'
    ---
    tags:
      - RealTime
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    contracts = []
    for stock in ALL_STOCK_NUM_LIST:
        contracts.append(token.Contracts.Stocks[stock])
    snapshots = token.snapshots(contracts)
    response = trade_agent_pb2.SnapshotResponse()
    for result in snapshots:
        tmp = trade_agent_pb2.SnapshotMessage()
        tmp.ts = result.ts
        tmp.code = result.code
        tmp.exchange = result.exchange
        tmp.open = result.open
        tmp.high = result.high
        tmp.low = result.low
        tmp.close = result.close
        tmp.tick_type = result.tick_type
        tmp.change_price = result.change_price
        tmp.change_rate = result.change_rate
        tmp.change_type = result.change_type
        tmp.average_price = result.average_price
        tmp.volume = result.volume
        tmp.total_volume = result.total_volume
        tmp.amount = result.amount
        tmp.total_amount = result.total_amount
        tmp.yesterday_volume = result.yesterday_volume
        tmp.buy_price = result.buy_price
        tmp.buy_volume = result.buy_volume
        tmp.sell_price = result.sell_price
        tmp.sell_volume = result.sell_volume
        tmp.volume_ratio = result.volume_ratio
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_all_snapshot, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/real-time/snapshot/tse', methods=['GET'])
def get_tse_snapshot():
    '''Get TSE latest snapshot and send to 'internal/snapshot_tse'
    ---
    tags:
      - RealTime
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    contracts = []
    contracts.append(token.Contracts.Indexs.TSE.TSE001)
    snapshots = token.snapshots(contracts)
    response = trade_agent_pb2.SnapshotResponse()
    for result in snapshots:
        tmp = trade_agent_pb2.SnapshotMessage()
        tmp.ts = result.ts
        tmp.code = result.code
        tmp.exchange = result.exchange
        tmp.open = result.open
        tmp.high = result.high
        tmp.low = result.low
        tmp.close = result.close
        tmp.tick_type = result.tick_type
        tmp.change_price = result.change_price
        tmp.change_rate = result.change_rate
        tmp.change_type = result.change_type
        tmp.average_price = result.average_price
        tmp.volume = result.volume
        tmp.total_volume = result.total_volume
        tmp.amount = result.amount
        tmp.total_amount = result.total_amount
        tmp.yesterday_volume = result.yesterday_volume
        tmp.buy_price = result.buy_price
        tmp.buy_volume = result.buy_volume
        tmp.sell_price = result.sell_price
        tmp.sell_volume = result.sell_volume
        tmp.volume_ratio = result.volume_ratio
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_tse_snapshot, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/tick', methods=['POST'])
def get_history_tick_by_stock_num_date():
    '''Get all history tick in one date and send to 'internal/history_tick'
    ---
    tags:
      - History
    parameters:
      - in: body
        name: stock with date
        description: Stock with date
        required: true
        schema:
          $ref: '#/definitions/StockWithDate'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockWithDate:
        type: object
        properties:
          stock_num:
            type: string
          date:
            type: string
    '''
    response = trade_agent_pb2.HistoryTickResponse()
    body = request.get_json()
    ticks = token.ticks(
        contract=token.Contracts.Stocks[body['stock_num']],
        date=body['date']
    )
    response.stock_num = body['stock_num']
    response.date = body['date']
    tmp_length = []
    total_count = len(ticks.ts)
    tmp_length.append(len(ticks.close))
    tmp_length.append(len(ticks.tick_type))
    tmp_length.append(len(ticks.volume))
    tmp_length.append(len(ticks.bid_price))
    tmp_length.append(len(ticks.bid_volume))
    tmp_length.append(len(ticks.ask_price))
    tmp_length.append(len(ticks.ask_volume))
    for length in tmp_length:
        if length - total_count != 0:
            return jsonify({'result': 'data broken'})
    for pos in range(total_count):
        tmp = trade_agent_pb2.HistoryTickMessage()
        tmp.ts = ticks.ts[pos]
        tmp.close = ticks.close[pos]
        tmp.volume = ticks.volume[pos]
        tmp.bid_price = ticks.bid_price[pos]
        tmp.bid_volume = ticks.bid_volume[pos]
        tmp.ask_price = ticks.ask_price[pos]
        tmp.ask_volume = ticks.ask_volume[pos]
        tmp.tick_type = ticks.tick_type[pos]
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_history_tick, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/tick/tse', methods=['POST'])
def get_tse_history_tick_by_date():
    '''Get tse tick in one date and send to 'internal/history_tick_tse'
    ---
    tags:
      - TSE
    parameters:
      - in: body
        name: fetch date
        description: fetch date
        required: true
        schema:
          $ref: '#/definitions/FetchDate'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      FetchDate:
        type: object
        properties:
          date:
            type: string
    '''
    response = trade_agent_pb2.HistoryTickResponse()
    body = request.get_json()
    ticks = token.ticks(
        contract=token.Contracts.Indexs.TSE.TSE001,
        date=body['date']
    )
    response.stock_num = 'TSE001'
    response.date = body['date']
    tmp_length = []
    total_count = len(ticks.ts)
    tmp_length.append(len(ticks.close))
    tmp_length.append(len(ticks.tick_type))
    tmp_length.append(len(ticks.volume))
    tmp_length.append(len(ticks.bid_price))
    tmp_length.append(len(ticks.bid_volume))
    tmp_length.append(len(ticks.ask_price))
    tmp_length.append(len(ticks.ask_volume))
    for length in tmp_length:
        if length - total_count != 0:
            return jsonify({'result': 'data broken'})
    for pos in range(total_count):
        tmp = trade_agent_pb2.HistoryTickMessage()
        tmp.ts = ticks.ts[pos]
        tmp.close = ticks.close[pos]
        tmp.volume = ticks.volume[pos]
        tmp.bid_price = ticks.bid_price[pos]
        tmp.bid_volume = ticks.bid_volume[pos]
        tmp.ask_price = ticks.ask_price[pos]
        tmp.ask_volume = ticks.ask_volume[pos]
        tmp.tick_type = ticks.tick_type[pos]
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_tse_thistory_tick, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/kbar', methods=['POST'])
def get_kbar_by_stock_num_date_range():
    '''Get all kbar in date range and send to 'internal/history_kbar'
    ---
    tags:
      - History
    parameters:
      - in: body
        name: stock with date range
        description: Stock with date range
        required: true
        schema:
          $ref: '#/definitions/StockWithDateRange'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockWithDateRange:
        type: object
        properties:
          stock_num:
            type: string
          start_date:
            type: string
          end_date:
            type: string
    '''
    response = trade_agent_pb2.HistoryKbarResponse()
    body = request.get_json()
    kbar = token.kbars(
        contract=token.Contracts.Stocks[body['stock_num']],
        start=body['start_date'],
        end=body['end_date'],
    )
    response.stock_num = body['stock_num']
    response.start_date = body['start_date']
    response.end_date = body['end_date']
    tmp_length = []
    total_count = len(kbar.ts)
    tmp_length.append(len(kbar.Close))
    tmp_length.append(len(kbar.Open))
    tmp_length.append(len(kbar.High))
    tmp_length.append(len(kbar.Low))
    tmp_length.append(len(kbar.Volume))
    for length in tmp_length:
        if length - total_count != 0:
            return jsonify({'result': 'data broken'})
    for pos in range(total_count):
        tmp = trade_agent_pb2.HistoryKbarMessage()
        tmp.ts = kbar.ts[pos]
        tmp.Close = kbar.Close[pos]
        tmp.Open = kbar.Open[pos]
        tmp.High = kbar.High[pos]
        tmp.Low = kbar.Low[pos]
        tmp.Volume = kbar.Volume[pos]
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_history_kbar, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/kbar/tse', methods=['POST'])
def get_tse_kbar_by_stock_num_date_range():
    '''Get tse kbar in date range and send to 'internal/history_kbar_tse'
    ---
    tags:
      - TSE
    parameters:
      - in: body
        name: Date range
        description: Date range
        required: true
        schema:
          $ref: '#/definitions/DateRange'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      DateRange:
        type: object
        properties:
          start_date:
            type: string
          end_date:
            type: string
    '''
    response = trade_agent_pb2.HistoryKbarResponse()
    body = request.get_json()
    kbar = token.kbars(
        contract=token.Contracts.Indexs.TSE.TSE001,
        start=body['start_date'],
        end=body['end_date'],
    )
    response.stock_num = 'TSE001'
    response.start_date = body['start_date']
    response.end_date = body['end_date']
    tmp_length = []
    total_count = len(kbar.ts)
    tmp_length.append(len(kbar.Close))
    tmp_length.append(len(kbar.Open))
    tmp_length.append(len(kbar.High))
    tmp_length.append(len(kbar.Low))
    tmp_length.append(len(kbar.Volume))
    for length in tmp_length:
        if length - total_count != 0:
            return jsonify({'result': 'data broken'})
    for pos in range(total_count):
        tmp = trade_agent_pb2.HistoryKbarMessage()
        tmp.ts = kbar.ts[pos]
        tmp.Close = kbar.Close[pos]
        tmp.Open = kbar.Open[pos]
        tmp.High = kbar.High[pos]
        tmp.Low = kbar.Low[pos]
        tmp.Volume = kbar.Volume[pos]
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_tse_history_kbar, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/close', methods=['POST'])
def get_lastcount_by_stock_arr_and_date():
    '''Get stock's last count and send to 'internal/lastcount'
    ---
    tags:
      - History
    parameters:
      - in: header
        name: X-Date
        description: Date
        required: true
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockArr:
        type: object
        properties:
          stock_num_arr:
            type: array
            items:
              $ref: '#/definitions/StockNum'
      StockNum:
          type: string
    '''
    date = request.headers['X-Date']
    body = request.get_json()
    stocks = body['stock_num_arr']
    response = trade_agent_pb2.HistoryCloseResponse()
    for stock in stocks:
        last_count = token.quote.ticks(
            contract=token.Contracts.Stocks[stock],
            date=date,
            query_type=sj.constant.TicksQueryType.LastCount,
            last_cnt=1,
        )
        tmp = trade_agent_pb2.HistoryCloseMessage()
        tmp.date = date
        tmp.code = stock
        tmp.close = last_count.close[0]
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_lastcount, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/close/tse', methods=['POST'])
def get_lastcount_tse_by_date():
    '''Get tse's last count and send to 'internal/lastcount_tse'
    ---
    tags:
      - TSE
    parameters:
      - in: header
        name: X-Date
        description: Date
        required: true
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    date = request.headers['X-Date']
    response = trade_agent_pb2.HistoryCloseResponse()
    last_count = token.quote.ticks(
        contract=token.Contracts.Indexs.TSE.TSE001,
        date=date,
        query_type=sj.constant.TicksQueryType.LastCount,
        last_cnt=1,
    )
    tmp = trade_agent_pb2.HistoryCloseMessage()
    tmp.date = date
    tmp.code = 'TSE001'
    tmp.close = last_count.close[0]
    response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_lastcount_tse, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/close/multi-date', methods=['POST'])
def get_lastcount_by_stock_arr_and_date_arr():
    '''Get stock's last count in a date range and send to 'internal/lastcount_multi_date'
    ---
    tags:
      - History
    parameters:
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockArrWithDateArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockArrWithDateArr:
        type: object
        properties:
          stock_num_arr:
            type: array
            items:
              $ref: '#/definitions/StockNum'
          date_arr:
            type: array
            items:
              $ref: '#/definitions/Date'
      StockNum:
          type: string
      Date:
          type: string
    '''
    body = request.get_json()
    stock_arr = body['stock_num_arr']
    date_arr = body['date_arr']
    response = trade_agent_pb2.HistoryCloseResponse()
    for stock in stock_arr:
        for date in date_arr:
            last_count = token.quote.ticks(
                contract=token.Contracts.Stocks[stock],
                date=date,
                query_type=sj.constant.TicksQueryType.LastCount,
                last_cnt=1,
            )
            tmp_close = 0
            if len(last_count.close) != 0:
                tmp_close = last_count.close[0]
            tmp = trade_agent_pb2.HistoryCloseMessage()
            tmp.date = date
            tmp.code = stock
            tmp.close = tmp_close
            response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_lastcount_multi_date, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/history/volumerank', methods=['GET'])
def get_volumerank_by_count_and_date():
    '''Get rank volume and send to 'internal/volumerank'
    ---
    tags:
      - History
    parameters:
      - in: header
        name: X-Count
        description: Count
        required: true
      - in: header
        name: X-Date
        description: Date
        required: true
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    rank_count = request.headers['X-Count']
    req_date = request.headers['X-Date']
    ranks = token.scanners(
        scanner_type=sj.constant.ScannerType.VolumeRank,
        count=rank_count,
        date=req_date,
    )
    response = trade_agent_pb2.VolumeRankResponse()
    response.count = int(rank_count)
    response.date = req_date
    for result in ranks:
        tmp = trade_agent_pb2.VolumeRankMessage()
        tmp.date = result.date
        tmp.code = result.code
        tmp.name = result.name
        tmp.ts = result.ts
        tmp.open = result.open
        tmp.high = result.high
        tmp.low = result.low
        tmp.close = result.close
        tmp.price_range = result.price_range
        tmp.tick_type = result.tick_type
        tmp.change_price = result.change_price
        tmp.change_type = result.change_type
        tmp.average_price = result.average_price
        tmp.volume = result.volume
        tmp.total_volume = result.total_volume
        tmp.amount = result.amount
        tmp.total_amount = result.total_amount
        tmp.yesterday_volume = result.yesterday_volume
        tmp.volume_ratio = result.volume_ratio
        tmp.buy_price = result.buy_price
        tmp.buy_volume = result.buy_volume
        tmp.sell_price = result.sell_price
        tmp.sell_volume = result.sell_volume
        tmp.bid_orders = result.bid_orders
        tmp.bid_volumes = result.bid_volumes
        tmp.ask_orders = result.ask_orders
        tmp.ask_volumes = result.ask_volumes
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_history_volumerank, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/subscribe/realtime-tick', methods=['POST'])
def subscribe_stock_realtime_tick_by_stock_arr():
    '''Subscribe realtime tick
    ---
    tags:
      - SubscribeRealTimeTick
    parameters:
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockNumArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    body = request.get_json()
    stocks = body['stock_num_arr']
    for stock in stocks:
        QUOTE_SUB_LIST.append(stock)
        CURRENT_STOCK_COUNT[stock] = 0
        logger.info('subscribe stock realtime tick %s', stock)
        token.quote.subscribe(
            token.Contracts.Stocks[stock],
            quote_type=sj.constant.QuoteType.Tick,
            version=sj.constant.QuoteVersion.v1
        )
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/unsubscribe/realtime-tick', methods=['POST'])
def unsubscribe_stock_realtime_tick_by_stock_arr():
    '''UnSubscribe realtime tick
    ---
    tags:
      - SubscribeRealTimeTick
    parameters:
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockNumArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    body = request.get_json()
    stocks = body['stock_num_arr']
    for stock in stocks:
        QUOTE_SUB_LIST.remove(stock)
        del CURRENT_STOCK_COUNT[stock]
        logger.info('unsubscribe stock realtime tick %s', stock)
        token.quote.unsubscribe(
            token.Contracts.Stocks[stock],
            quote_type=sj.constant.QuoteType.Tick,
            version=sj.constant.QuoteVersion.v1
        )
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/unsubscribeall/realtime-tick', methods=['GET'])
def unsubscribe_all_stock_realtime_tick():
    '''Unubscribe all realtime tick
    ---
    tags:
      - SubscribeRealTimeTick
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    global QUOTE_SUB_LIST  # pylint: disable=global-statement
    if len(QUOTE_SUB_LIST) != 0:
        for stock in QUOTE_SUB_LIST:
            logger.info('unsubscribe stock realtime tick %s', stock)
            token.quote.unsubscribe(
                token.Contracts.Stocks[stock],
                quote_type=sj.constant.QuoteType.Tick,
                version=sj.constant.QuoteVersion.v1
            )
        QUOTE_SUB_LIST = []
        CURRENT_STOCK_COUNT.clear()
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/subscribe/bid-ask', methods=['POST'])
def subscribe_stock_realtime_bidask_by_stock_arr():
    '''Subscribe bid-ask
    ---
    tags:
      - SubscribeBidAsk
    parameters:
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockNumArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockNumArr:
        type: object
        properties:
          stock_num_arr:
            type: array
            items:
              $ref: '#/definitions/StockNum'
      StockNum:
        type: string
    '''
    body = request.get_json()
    stocks = body['stock_num_arr']
    for stock in stocks:
        BIDASK_SUB_LIST.append(stock)
        logger.info('subscribe stock realtime bid-ask %s', stock)
        token.quote.subscribe(
            token.Contracts.Stocks[stock],
            quote_type=sj.constant.QuoteType.BidAsk,
            version=sj.constant.QuoteVersion.v1
        )
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/unsubscribe/bid-ask', methods=['POST'])
def unsubscribe_stock_realtime_bidask_by_stock_arr():
    '''UnSubscribe bid-ask
    ---
    tags:
      - SubscribeBidAsk
    parameters:
      - in: body
        name: stock array
        description: Stock array
        required: true
        schema:
          $ref: '#/definitions/StockNumArr'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      StockNumArr:
        type: object
        properties:
          stock_num_arr:
            type: array
            items:
              $ref: '#/definitions/StockNum'
      StockNum:
        type: string
    '''
    body = request.get_json()
    stocks = body['stock_num_arr']
    for stock in stocks:
        BIDASK_SUB_LIST.remove(stock)
        logger.info('unsubscribe stock realtime bid-ask %s', stock)
        token.quote.unsubscribe(
            token.Contracts.Stocks[stock],
            quote_type=sj.constant.QuoteType.BidAsk,
            version=sj.constant.QuoteVersion.v1
        )
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/unsubscribeall/bid-ask', methods=['GET'])
def unsubscribe_all_stock_realtime_bidask():
    '''Unsubscribe all bid-ask
    ---
    tags:
      - SubscribeBidAsk
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    global BIDASK_SUB_LIST  # pylint: disable=global-statement
    if len(BIDASK_SUB_LIST) != 0:
        for stock in BIDASK_SUB_LIST:
            logger.info('unsubscribe stock realtime bid-ask %s', stock)
            token.quote.unsubscribe(
                token.Contracts.Stocks[stock],
                quote_type=sj.constant.QuoteType.BidAsk,
                version=sj.constant.QuoteVersion.v1
            )
        BIDASK_SUB_LIST = []
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/trade/buy', methods=['POST'])
def buy_stock():
    '''Buy stock
    ---
    tags:
      - Trade
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
      - in: body
        name: order
        description: Buy order
        required: true
        schema:
          $ref: '#/definitions/Order'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/OrderSuccess'
      500:
        description: Server Not Ready
    definitions:
      Order:
        type: object
        properties:
          stock:
            type: string
          price:
            type: number
          quantity:
            type: integer
      OrderSuccess:
        type: object
        properties:
          status:
            type: string
          order_id:
            type: string
    '''
    sim = request.headers['X-Simulate']
    body = request.get_json()
    contract = token.Contracts.Stocks[body['stock']]
    order = token.Order(
        price=body['price'],
        quantity=body['quantity'],
        action=sj.constant.Action.Buy,
        price_type=sj.constant.StockPriceType.LMT,
        order_type=sj.constant.TFTOrderType.ROD,
        order_lot=sj.constant.TFTStockOrderLot.Common,
        account=token.stock_account
    )
    if int(sim) == 0:
        trade = token.place_order(contract, order)
        if trade is not None and trade.order.id != '':
            if trade.status.status == sj.constant.Status.Cancelled:
                trade.status.status = 'Canceled'
            return jsonify({
                'status': trade.status.status,
                'order_id': trade.order.id,
            })
    else:
        order_status = sj.order.OrderStatus(
            id=''.join(random.choice(string.ascii_lowercase+string.octdigits) for _ in range(8)),
            status=sj.constant.Status.Submitted,
            status_code='',
            order_datetime=datetime.now(),
            deals=[],
        )
        sim_order = sj.order.Trade(
            contract=contract,
            order=order,
            status=order_status,
        )
        with simulation_count_lock:
            if CURRENT_STOCK_COUNT[body['stock']] < 0:
                if body['quantity']+CURRENT_STOCK_COUNT[body['stock']] > 0:
                    return jsonify({
                        'status': 'fail',
                        'order_id': '',
                    })
        threading.Thread(target=finish_simulation_order, args=(sim_order, random.randrange(15)+1)).start()
        return jsonify({
            'status': sim_order.status.status,
            'order_id': sim_order.status.id,
        })
    return jsonify({
        'status': 'fail',
        'order_id': '',
    })


@ api.route('/sinopac-mq-srv/trade/sell', methods=['POST'])
def sell_stock():
    '''Sell stock
    ---
    tags:
      - Trade
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
      - in: body
        name: order
        description: Sell order
        required: true
        schema:
          $ref: '#/definitions/Order'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/OrderSuccess'
      500:
        description: Server Not Ready
    definitions:
      Order:
        type: object
        properties:
          stock:
            type: string
          price:
            type: number
          quantity:
            type: integer
    '''
    sim = request.headers['X-Simulate']
    body = request.get_json()
    contract = token.Contracts.Stocks[body['stock']]
    order = token.Order(
        price=body['price'],
        quantity=body['quantity'],
        action=sj.constant.Action.Sell,
        price_type=sj.constant.StockPriceType.LMT,
        order_type=sj.constant.TFTOrderType.ROD,
        order_lot=sj.constant.TFTStockOrderLot.Common,
        account=token.stock_account
    )
    if int(sim) == 0:
        trade = token.place_order(contract, order)
        if trade is not None and trade.order.id != '':
            if trade.status.status == sj.constant.Status.Cancelled:
                trade.status.status = 'Canceled'
            return jsonify({
                'status': trade.status.status,
                'order_id': trade.order.id,
            })
    else:
        order_status = sj.order.OrderStatus(
            id=''.join(random.choice(string.ascii_lowercase+string.octdigits) for _ in range(8)),
            status=sj.constant.Status.Submitted,
            status_code='',
            order_datetime=datetime.now(),
            deals=[],
        )
        sim_order = sj.order.Trade(
            contract=contract,
            order=order,
            status=order_status,
        )
        with simulation_count_lock:
            if body['quantity'] > CURRENT_STOCK_COUNT[body['stock']]:
                return jsonify({
                    'status': 'fail',
                    'order_id': '',
                })
        threading.Thread(target=finish_simulation_order, args=(sim_order, random.randrange(15)+1)).start()
        return jsonify({
            'status': sim_order.status.status,
            'order_id': sim_order.status.id,
        })
    return jsonify({
        'status': 'fail',
        'order_id': '',
    })


@ api.route('/sinopac-mq-srv/trade/sell_first', methods=['POST'])
def sell_first_stock():
    '''Sell stock first
    ---
    tags:
      - Trade
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
      - in: body
        name: order
        description: Sell stock first
        required: true
        schema:
          $ref: '#/definitions/Order'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/OrderSuccess'
      500:
        description: Server Not Ready
    definitions:
      Order:
        type: object
        properties:
          stock:
            type: string
          price:
            type: number
          quantity:
            type: integer
    '''
    sim = request.headers['X-Simulate']
    body = request.get_json()
    contract = token.Contracts.Stocks[body['stock']]
    order = token.Order(
        price=body['price'],
        quantity=body['quantity'],
        action=sj.constant.Action.Sell,
        price_type=sj.constant.StockPriceType.LMT,
        order_type=sj.constant.TFTOrderType.ROD,
        order_lot=sj.constant.TFTStockOrderLot.Common,
        first_sell=sj.constant.StockFirstSell.Yes,
        account=token.stock_account
    )
    if int(sim) == 0:
        trade = token.place_order(contract, order)
        if trade is not None and trade.order.id != '':
            if trade.status.status == sj.constant.Status.Cancelled:
                trade.status.status = 'Canceled'
            return jsonify({
                'status': trade.status.status,
                'order_id': trade.order.id,
            })
    else:
        order_status = sj.order.OrderStatus(
            id=''.join(random.choice(string.ascii_lowercase+string.octdigits) for _ in range(8)),
            status=sj.constant.Status.Submitted,
            status_code='',
            order_datetime=datetime.now(),
            deals=[],
        )
        sim_order = sj.order.Trade(
            contract=contract,
            order=order,
            status=order_status,
        )
        with simulation_count_lock:
            if CURRENT_STOCK_COUNT[body['stock']] > 0:
                return jsonify({
                    'status': 'fail',
                    'order_id': '',
                })
        threading.Thread(target=finish_simulation_order, args=(sim_order, random.randrange(15)+1)).start()
        return jsonify({
            'status': sim_order.status.status,
            'order_id': sim_order.status.id,
        })
    return jsonify({
        'status': 'fail',
        'order_id': '',
    })


def finish_simulation_order(order: sj.order.Trade, wait: int):
    HISTORY_ORDERS.append(order)
    with simulation_count_lock:
        buy_later = False

        if order.order.action == sj.constant.Action.Buy and CURRENT_STOCK_COUNT[order.contract.code] < 0:
            buy_later = True
            CURRENT_STOCK_COUNT[order.contract.code] += order.order.quantity
            logger.warning('%s has %d', order.contract.code, CURRENT_STOCK_COUNT[order.contract.code])

        if order.order.action == sj.constant.Action.Sell:
            CURRENT_STOCK_COUNT[order.contract.code] -= order.order.quantity
            logger.warning('%s has %d', order.contract.code, CURRENT_STOCK_COUNT[order.contract.code])

        # 5% may fail
        random_number = random.randrange(100)+1
        if random_number < 6:
            if buy_later is True:
                CURRENT_STOCK_COUNT[order.contract.code] -= order.order.quantity
                logger.warning('%s has %d', order.contract.code, CURRENT_STOCK_COUNT[order.contract.code])

            if order.order.action == sj.constant.Action.Sell:
                CURRENT_STOCK_COUNT[order.contract.code] += order.order.quantity
                logger.warning('%s has %d', order.contract.code, CURRENT_STOCK_COUNT[order.contract.code])
            return

    time.sleep(wait)
    with simulation_count_lock:
        for sim in HISTORY_ORDERS:
            if sim.order.action == sj.constant.Action.Buy and order.status.id == sim.status.id and buy_later is False:
                CURRENT_STOCK_COUNT[sim.contract.code] += sim.order.quantity
                logger.warning('%s has %d', sim.contract.code, CURRENT_STOCK_COUNT[sim.contract.code])

            if sim.status.id == order.status.id:
                sim.status.status = sj.constant.Status.Filled


@ api.route('/sinopac-mq-srv/trade/cancel', methods=['POST'])
def cancel_stock():
    '''Cancel order
    ---
    tags:
      - Trade
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
      - in: body
        name: order id
        description: Cancel Order ID
        required: true
        schema:
          $ref: '#/definitions/OrderID'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      OrderID:
        type: object
        properties:
          order_id:
            type: string
    '''
    sim = request.headers['X-Simulate']
    body = request.get_json()
    if int(sim) == 0:
        cancel_order = None
        times = int()
        while True:
            mutex_update_status(-1)
            for order in HISTORY_ORDERS:
                if order.status.id == body['order_id']:
                    cancel_order = order
            if cancel_order is not None or times >= 10:
                break
            times += 1
        if cancel_order is None:
            return jsonify({'result': 'cancel order not found'})
        if cancel_order.status.status == sj.constant.Status.Cancelled:
            return jsonify({'result': 'order already be canceled'})
        token.cancel_order(cancel_order)
        times = 0
        while True:
            if times >= 10:
                break
            mutex_update_status(-1)
            for order in HISTORY_ORDERS:
                if order.status.id == body['order_id'] and order.status.status == sj.constant.Status.Cancelled:
                    return jsonify({'result': 'success'})
            times += 1
    else:
        for sim in HISTORY_ORDERS:
            if sim.status.id == body['order_id'] and sim.status.status != sj.constant.Status.Cancelled:
                sim.status.status = sj.constant.Status.Cancelled
                return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/trade/status', methods=['GET'])
def get_order_status():
    '''Get order status
    ---
    tags:
      - TradeStatus
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    sim = request.headers['X-Simulate']
    if int(sim) == 0:
        try:
            mutex_update_status(0)
        except sj.error.TokenError:
            send_token_expired_event()
        return jsonify({'result': 'success'})
    response = trade_agent_pb2.OrderStatusHistoryResponse()
    if len(HISTORY_ORDERS) == 0:
        return jsonify({'result': 'success'})
    for order in HISTORY_ORDERS:
        order_price = int()
        if order.status.status == sj.constant.Status.Cancelled:
            order.status.status = 'Canceled'
        if order.status.modified_price != 0:
            order_price = order.status.modified_price
        else:
            order_price = order.order.price
        tmp = trade_agent_pb2.OrderStatusHistoryMessage()
        tmp.code = order.contract.code
        tmp.action = order.order.action
        tmp.price = order_price
        tmp.quantity = order.order.quantity
        tmp.order_id = order.status.id
        tmp.status = order.status.status
        tmp.order_time = datetime.strftime(order.status.order_datetime, '%Y-%m-%d %H:%M:%S')
        response.data.append(tmp)
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return jsonify({'result': 'mq broker is disconnected'})
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_order_status, payload=response.SerializeToString(), qos=2, retain=False)
        return jsonify({'result': 'success'})
    return jsonify({'result': 'fail'})


@ api.route('/sinopac-mq-srv/trade/order/status', methods=['GET'])
def get_order_status_from_local_by_order_id():
    '''Fetch Order Status by order id
    ---
    tags:
      - TradeStatus
    parameters:
      - in: header
        name: X-Simulate
        description: 0 = normal, 1 = simulate
        required: true
      - in: header
        name: X-Order-ID
        description: Order ID
        required: true
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    sim = request.headers['X-Simulate']
    order_id = request.headers['X-Order-ID']
    if int(sim) == 0:
        mutex_update_status(-1)
    if len(HISTORY_ORDERS) == 0:
        return jsonify({
            'status': 'fail',
            'order_id': '',
        })
    for order in HISTORY_ORDERS:
        if order.status.id == order_id:
            if order.status.status == sj.constant.Status.Cancelled:
                order.status.status = 'Canceled'
            return jsonify({
                'status': order.status.status,
                'order_id': order.status.id,
            })
    return jsonify({
        'status': 'fail',
        'order_id': '',
    })


@ api.route('/sinopac-mq-srv/system/healthcheck', methods=['GET'])
def get_health_check():
    '''Server health check
    ---
    tags:
      - System
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/HealthResponse'
      500:
        description: Server Not Ready
    definitions:
      HealthResponse:
        type: object
        properties:
          result:
            type: string
          up_time_min:
            type: number
          server_token:
            type: string
    '''
    return jsonify({
        'result': 'success',
        'up_time_min': UP_TIME,
        'server_token': server_token,
    })


@ api.route('/sinopac-mq-srv/system/mq-connect', methods=['POST'])
def get_mq_conf_to_connect():
    '''Post to connect mqtt broker
    ---
    tags:
      - System
    parameters:
      - in: body
        name: mq_conf
        description: MQTT parameters
        required: true
        schema:
          $ref: '#/definitions/MQConf'
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    definitions:
      MQConf:
        type: object
        properties:
          host:
            type: string
          port:
            type: string
          user:
            type: string
          password:
            type: string
    '''
    body = request.get_json()
    mq_host = body['host']
    mq_port = body['port']
    mq_user_name = body['user']
    mq_password = body['passwd']
    status = connect_mqtt_broker(
        mq_host,
        int(mq_port),
        mq_user_name,
        mq_password
    )
    if status == -1:
        return jsonify({'result': 'fail'})
    return jsonify({'result': 'success'})


@ api.route('/sinopac-mq-srv/system/restart', methods=['GET'])
def system_restart():
    '''Restart
    ---
    tags:
      - System
    responses:
      200:
        description: Success Response
        name: result
        schema:
          $ref: '#/definitions/Result'
      500:
        description: Server Not Ready
    '''
    if deployment == 'docker':
        threading.Thread(target=run_pkill).start()
        return jsonify({'result': 'success'})
    return jsonify({'result': 'you should be in the docker container'})


def mutex_update_status(timeout: int):
    '''Mutex for update status'''
    if timeout == 0:
        token.update_status(timeout=0, cb=order_status_callback)
    elif timeout == -1:
        with mutex:
            global HISTORY_ORDERS  # pylint: disable=global-statement
            token.update_status()
            HISTORY_ORDERS = token.list_trades()


def order_status_callback(reply: typing.List[sj.order.Trade]):
    '''Sinopac order status's callback'''
    with mutex:
        response = trade_agent_pb2.OrderStatusHistoryResponse()
        if len(reply) != 0:
            for order in reply:
                res = trade_agent_pb2.OrderStatusHistoryMessage()
                if order.status.status == sj.constant.Status.Cancelled:
                    order.status.status = 'Canceled'
                if order.status.order_datetime is None:
                    order.status.order_datetime = datetime.now()
                order_price = int()
                if order.status.modified_price != 0:
                    order_price = order.status.modified_price
                else:
                    order_price = order.order.price
                res.code = order.contract.code
                res.action = order.order.action
                res.price = order_price
                res.quantity = order.order.quantity
                res.order_id = order.status.id
                res.status = order.status.status
                res.order_time = datetime.strftime(order.status.order_datetime, '%Y-%m-%d %H:%M:%S')
                response.data.append(res)
            if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
                logger.warning(response)
                return
            if response.ByteSize != 0:
                MQTT_CLIENT.publish(topic=mq_topic.topic_order_status, payload=response.SerializeToString(), qos=2, retain=False)


def quote_callback_v1(exchange: sj.Exchange, tick: sj.TickSTKv1):
    '''Sinopac's quiote callback v1'''
    response = trade_agent_pb2.RealTimeTickResponse()
    response.exchange = exchange
    response.tick.code = tick.code
    response.tick.date_time = datetime.strftime(tick.datetime, '%Y-%m-%d %H:%M:%S.%f')
    response.tick.open = tick.open
    response.tick.avg_price = tick.avg_price
    response.tick.close = tick.close
    response.tick.high = tick.high
    response.tick.low = tick.low
    response.tick.amount = tick.amount
    response.tick.total_amount = tick.total_amount
    response.tick.volume = tick.volume
    response.tick.total_volume = tick.total_volume
    response.tick.tick_type = tick.tick_type
    response.tick.chg_type = tick.chg_type
    response.tick.price_chg = tick.price_chg
    response.tick.pct_chg = tick.pct_chg
    response.tick.bid_side_total_vol = tick.bid_side_total_vol
    response.tick.ask_side_total_vol = tick.ask_side_total_vol
    response.tick.bid_side_total_cnt = tick.bid_side_total_cnt
    response.tick.ask_side_total_cnt = tick.ask_side_total_cnt
    response.tick.suspend = tick.suspend
    response.tick.simtrade = tick.simtrade
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_realtime_tick, payload=response.SerializeToString(), qos=2, retain=False)


def bid_ask_callback(exchange: sj.Exchange, bidask: sj.BidAskSTKv1):
    '''Sinopac's bidask callback'''
    response = trade_agent_pb2.RealTimeBidAskResponse()
    response.exchange = exchange
    response.bid_ask.code = bidask.code
    response.bid_ask.date_time = datetime.strftime(bidask.datetime, '%Y-%m-%d %H:%M:%S.%f')
    response.bid_ask.bid_price.extend(bidask.bid_price)
    response.bid_ask.bid_volume.extend(bidask.bid_volume)
    response.bid_ask.diff_bid_vol.extend(bidask.diff_bid_vol)
    response.bid_ask.ask_price.extend(bidask.ask_price)
    response.bid_ask.ask_volume.extend(bidask.ask_volume)
    response.bid_ask.diff_ask_vol.extend(bidask.diff_ask_vol)
    response.bid_ask.suspend = bidask.suspend
    response.bid_ask.simtrade = bidask.simtrade
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_realtime_bidask, payload=response.SerializeToString(), qos=2, retain=False)


def event_callback(resp_code: int, event_code: int, info: str, event: str):
    '''Sinopac's event callback'''
    response = trade_agent_pb2.EventResponse()
    response.resp_code = resp_code
    response.event_code = event_code
    response.info = info
    response.event = event
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_trade_event, payload=response.SerializeToString(), qos=2, retain=False)


def send_token_expired_event():
    '''Sinopac's event callback'''
    response = trade_agent_pb2.EventResponse()
    response.resp_code = 500
    response.event_code = 401
    response.info = 'Please resubscribe if there exits subscription'
    response.event = 'Token is expired.'
    if MQTT_CLIENT.is_connected() is False and MQTT_CONNECTING is False:
        logger.warning(response)
        return
    if response.ByteSize != 0:
        MQTT_CLIENT.publish(topic=mq_topic.topic_trade_event, payload=response.SerializeToString(), qos=2, retain=False)


def fill_all_stock_local_list():
    '''Fill ALL_STOCK_NUM_LIST'''
    global ALL_STOCK_NUM_LIST  # pylint: disable=global-statement
    ALL_STOCK_NUM_LIST = []
    for all_contract in token.Contracts.Stocks:
        for day_trade_stock in all_contract:
            if day_trade_stock.day_trade == 'Yes':
                ALL_STOCK_NUM_LIST.append(day_trade_stock.code)
    while True:
        if len(ALL_STOCK_NUM_LIST) != 0:
            break
    logger.info('Filling ALL_STOCK_NUM_LIST, total: %d', len(ALL_STOCK_NUM_LIST))


def run_pkill():
    '''Restart in container'''
    time.sleep(1)
    os._exit(0)  # pylint: disable=protected-access


def connection_err():
    '''Error counter'''
    global ERROR_TIMES  # pylint: disable=global-statement
    ERROR_TIMES += 1
    if ERROR_TIMES > 30:
        threading.Thread(target=run_pkill).start()


def reset_err():
    '''Error reset'''
    global ERROR_TIMES  # pylint: disable=global-statement
    record = int()
    while True:
        if ERROR_TIMES == record and record > 0:
            logger.warning('%d error reset', ERROR_TIMES)
            ERROR_TIMES = 0
        record = ERROR_TIMES
        time.sleep(30)


def place_order_callback(order_state: sj.constant.OrderState, order: dict):
    '''Place order callback'''
    if search('DEAL', order_state) is None:
        logger.info('%s %s %.2f %d %s %d %s %s %s %s',
                    order['contract']['code'],
                    order['order']['action'],
                    order['order']['price'],
                    order['order']['quantity'],
                    order_state,
                    order['status']['exchange_ts'],
                    order['order']['id'],
                    order['operation']['op_type'],
                    order['operation']['op_code'],
                    order['operation']['op_msg'],
                    )
    else:
        logger.info('%s %s %.2f %d %s %d %s %s',
                    order['code'],
                    order['action'],
                    order['price'],
                    order['quantity'],
                    order_state,
                    order['ts'],
                    order['trade_id'],
                    order['exchange_seq'],
                    )


def login_callback(security_type: sj.constant.SecurityType):
    '''Login event callback'''
    with login_mutex:
        global SINOPAC_LOGIN_STATUS  # pylint: disable=global-statement
        if security_type.value in ('STK', 'IND', 'FUT', 'OPT'):
            SINOPAC_LOGIN_STATUS += 25
            logger.warning('login progress: %d%%, %s', SINOPAC_LOGIN_STATUS, security_type)


def sinopac_login():
    '''Login into sinopac'''
    token.login(
        person_id=sys.argv[2],
        passwd=sys.argv[3],
        contracts_cb=login_callback
    )
    for account in token.list_accounts():
        logger.info(account)
    # while True:
    #     if SINOPAC_LOGIN_STATUS == 100:
    #         break
    token.activate_ca(
        ca_path='./data/ca_sinopac.pfx',
        ca_passwd=sys.argv[4],
        person_id=sys.argv[2],
    )


def set_sinopac_callback():
    token.set_order_callback(place_order_callback)
    token.quote.set_event_callback(event_callback)
    token.quote.set_on_tick_stk_v1_callback(quote_callback_v1)
    token.quote.set_on_bidask_stk_v1_callback(bid_ask_callback)
    # token.quote.set_on_tick_fop_v1_callback(future_quote_callback)


def server_up_time():
    '''Record server up time'''
    global UP_TIME  # pylint: disable=global-statement
    while True:
        time.sleep(60)
        UP_TIME += 1


def mqtt_on_lost(client: paho.Client, userdata: None, rc: int):
    logger.info('MQTT Broker disconnected, unsubscribe all')
    global QUOTE_SUB_LIST  # pylint: disable=global-statement
    if len(QUOTE_SUB_LIST) != 0:
        for stock in QUOTE_SUB_LIST:
            logger.info('unsubscribe stock realtime tick %s', stock)
            token.quote.unsubscribe(
                token.Contracts.Stocks[stock],
                quote_type=sj.constant.QuoteType.Tick,
                version=sj.constant.QuoteVersion.v1
            )
        QUOTE_SUB_LIST = []
    global BIDASK_SUB_LIST  # pylint: disable=global-statement
    if len(BIDASK_SUB_LIST) != 0:
        for stock in BIDASK_SUB_LIST:
            logger.info('unsubscribe stock realtime bid-ask %s', stock)
            token.quote.unsubscribe(
                token.Contracts.Stocks[stock],
                quote_type=sj.constant.QuoteType.BidAsk,
                version=sj.constant.QuoteVersion.v1
            )
        BIDASK_SUB_LIST = []
    logger.info('Client: %s, Userdate: %s, RC: %d', client, userdata, rc)


def connect_mqtt_broker(mq_host: str, mq_port: int, user_name: str, passwd: str):
    '''Connect to MQTT Broker'''
    global MQTT_CLIENT, MQTT_CONNECTING  # pylint: disable=global-statement
    MQTT_CONNECTING = True
    MQTT_CLIENT.loop_stop()
    MQTT_CLIENT.disconnect()
    logger.info('New MQTT connection')
    new_client = paho.Client(client_id="sinopac-srv-" + str(random.randrange(10000)))
    new_client.tls_set(
        ca_certs="./configs/certs/ca_crt.pem",
        certfile="./configs/certs/client_crt.pem",
        keyfile="./configs/certs/client_key.pem",
        cert_reqs=ssl.CERT_NONE,
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )
    new_client.username_pw_set(user_name, passwd)
    new_client.tls_insecure_set(True)
    new_client.connect(
        host=mq_host,
        port=mq_port,
        keepalive=60,
    )
    new_client.loop_start()
    new_client.on_disconnect = mqtt_on_lost
    MQTT_CLIENT = new_client
    MQTT_CONNECTING = False
    return 0


if __name__ == '__main__':
    threading.Thread(target=reset_err).start()
    threading.Thread(target=server_up_time).start()
    set_sinopac_callback()
    sinopac_login()
    fill_all_stock_local_list()
    logger.info('Server Token: %s', server_token)
    serve(api, host='0.0.0.0', port=sys.argv[1])
