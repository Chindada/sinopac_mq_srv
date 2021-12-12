# from shioaji import BidAskSTKv1, TickSTKv1, Exchange, constant, error, TickFOPv1

# @ api.route('/sinopac-mq-srv/subscribe/future', methods=['POST'])
# def sub_future():
#     '''Subscribe future
#     ---
#     tags:
#       - Subscribe future
#     parameters:
#       - in: body
#         name: future array
#         description: future array
#         required: true
#         schema:
#           $ref: '#/definitions/FutureNumArr'
#     responses:
#       200:
#         description: Success Response
#       500:
#         description: Server Not Ready
#     definitions:
#       FutureNumArr:
#         type: object
#         properties:
#           future_num_arr:
#             type: array
#             items:
#               $ref: '#/definitions/FutureNum'
#       FutureNum:
#         type: string
#     '''
#     body = request.get_json()
#     futures = body['future_num_arr']
#     for future in futures:
#         FUTURE_SUB_LIST.append(future)
#         logger.info('subscribe future %s', future)
#         token.quote.subscribe(
#             token.Contracts.Futures[future],
#             quote_type=sj.constant.QuoteType.Tick,
#             version=sj.constant.QuoteVersion.v1
#         )
#     return jsonify({'status': 'success'})


# @ api.route('/sinopac-mq-srv/unsubscribe/future', methods=['POST'])
# def unsub_future():
#     '''UnSubscribe future
#     ---
#     tags:
#       - Subscribe future
#     parameters:
#       - in: body
#         name: future array
#         description: future array
#         required: true
#         schema:
#           $ref: '#/definitions/FutureNumArr'
#     responses:
#       200:
#         description: Success Response
#       500:
#         description: Server Not Ready
#     '''
#     body = request.get_json()
#     futures = body['future_num_arr']
#     for future in futures:
#         FUTURE_SUB_LIST.remove(future)
#         logger.info('unsubscribe future %s', future)
#         token.quote.unsubscribe(
#             token.Contracts.Futures[future],
#             quote_type=sj.constant.QuoteType.Tick,
#             version=sj.constant.QuoteVersion.v1
#         )
#     return jsonify({'status': 'success'})


# @ api.route('/sinopac-mq-srv/unsubscribeall/future', methods=['GET'])
# def unstream_all_future():
#     '''Unubscribe all future
#     ---
#     tags:
#       - Subscribe future
#     responses:
#       200:
#         description: Success Response
#       500:
#         description: Server Not Ready
#     '''
#     global FUTURE_SUB_LIST  # pylint: disable=global-statement
#     if len(FUTURE_SUB_LIST) != 0:
#         for future in FUTURE_SUB_LIST:
#             logger.info('unsubscribe future %s', future)
#             token.quote.unsubscribe(
#                 token.Contracts.Futures[future],
#                 quote_type=sj.constant.QuoteType.Tick,
#                 version=sj.constant.QuoteVersion.v1
#             )
#         FUTURE_SUB_LIST = []
#     return jsonify({'status': 'success'})

# def future_quote_callback(exchange: Exchange, tick: TickFOPv1):
#     '''Future callback'''
#     logger.info(exchange)
#     logger.info(tick)
