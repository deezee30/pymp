import os
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager

# # get real Binance user API keys
binance_api = os.environ.get("binance_api")
binance_secret = os.environ.get("binance_secret")

# test API keys
test_api = "SPeY1nXjquzNpTNt8Iz1Wd3liuXVxLqNS1Zlwy6KAZl5XrwMQeLMvvzZEVrIX0ZT"
test_secret = "FMZZ8y8BBMuukqHG1VzInt2gAYKchqBowgLgZh0EQAf5UMgSYH2H2JzgPQYlOdDA"

btc_live_price = {'error': False}

def btc_trade_history(msg):
    ''' define how to process incoming WebSocket messages '''
    if msg['e'] != 'error':
        print(msg['c'])
        btc_live_price['last'] = msg['c']
        btc_live_price['bid'] = msg['b']
        btc_live_price['last'] = msg['a']
    else:
        btc_live_price['error'] = True
        print("Error")


if __name__ == "__main__":
    # create new Binance client
    client = Client(test_api, test_secret)

    # change API endpoint for testing
    client.API_URL = "https://testnet.binance.vision/api"

    client_info = client.get_account()  # get account info

    btc = client.get_asset_balance(asset="BTC")  # get amount of BTC available

    # init and start the WebSocket
    bsm = BinanceSocketManager(client)
    conn_key = bsm.start_symbol_ticker_socket('BTCUSDT', btc_trade_history)
    bsm.start()

    # valid timeframe intervals - 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M

    while 1:
        pass

    # stop websocket
    bsm.stop_socket(conn_key)
    # properly terminate WebSocket
    reactor.stop()
