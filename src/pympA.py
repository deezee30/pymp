import os  # Util
import time  # Timing
import json  # JSON
import argparse  # Command parser
import threading  # multithreading

# python-binance lib
from binance.enums import *
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

DEV_KEY_FILE = "dev-key.json"  # dev key file
DEV_KEY_API = "api-key"  # api-key identifier
DEV_KEY_SECRET = "secret-key"  # secret-key identifier
live_price = {'error': False}  # live price for the SHT/BTC trade pair
LIVE_PRICE_LOCK = threading.Lock()  # lock for acquiring the live_price critical section

def input_keys():
    """
    prompt user to enter their Binance API public and private keys

    :return: public key string, private key string
    """
    print("Please insert keys before usage.")
    pub = input("Enter public key: ").strip()
    priv = input("Enter private key: ").strip()

    return pub, priv

def update_price(msg):
    """
        callback function

        process incoming WebSocket price update for SHT/BTC trades
    """
    with LIVE_PRICE_LOCK:
        if msg['e'] != 'error':
            live_price['last'] = float(msg['c']) # current price
            print(f"new price: {live_price['last']}")
        else:
            live_price['error'] = True
            print("Error in price update.")

def sell():
    """
        sell all SHT coins in wallet for BTC
    """
    coin_amt = float(client.get_asset_balance(asset=coin)['free'])
    pump_sell_t1 = int(time.time() * 1000)  # ms
    try:
        sell_order = client.create_test_order(symbol=symbol,
                                              side="SELL",
                                              type="MARKET",
                                              quantity=coin_amt)  # change to create_order
    except BinanceAPIException as e:
        # error handling goes here
        print(e)
    except BinanceOrderException as e:
        # error handling goes here
        print(e)
    # test sell case
    if "status" not in sell_order:
        print("TEST: order response is empty!")
        sell_order['status'] = 'FILLED'
        sell_order["transactTime"] = int(time.time() * 1000)
        sell_order["executedQty"] = 1
        sell_order['price'] = 2
        # exit(0)
    # real sell case
    if sell_order["status"] == "FILLED":
        pump_sell_ms = sell_order["transactTime"] - pump_sell_t1  # Time taken to sell in ms
        executedQty = sell_order["executedQty"]
        sell_price = sell_order['price']
        print(f"Sold {executedQty} {coin} in {pump_sell_ms} ms for {sell_price} BTC per {coin}.")
    else:
        print(f"Order has not been filled. Response:")
        print(sell_order)
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Pump n dump automated bot')
    parser.add_argument("--btc", type=str, default=None, required=True, help="amount of BTC to use to purchase coin")
    parser.add_argument("--wait", type=int, default=0, required=True,
                        help="Time to wait between buy and sell, in seconds")
    parser.add_argument("--pct", type=int, default=0, required=False,
                        help="Percentage increase from buy price at which to sell")
    args = parser.parse_args()

    # Handle API key load
    if os.path.exists(DEV_KEY_FILE):
        # Load key file
        with open(DEV_KEY_FILE, 'r') as f:
            keys = json.loads(f.read())

        # incomplete key file
        if DEV_KEY_API not in keys or DEV_KEY_SECRET not in keys:
            # get new keys
            pub, priv = input_keys()
            keys[DEV_KEY_API] = pub
            keys[DEV_KEY_SECRET] = priv
            # update key file
            with open(DEV_KEY_FILE, 'w') as f:
                json.dump(keys, f, indent=4)
                print(f"Generated '{DEV_KEY_FILE}'")

    else:
        # Create blank keys
        keys = {
            DEV_KEY_API: "",
            DEV_KEY_SECRET: ""
        }

        # get new keys
        pub, priv = input_keys()
        keys[DEV_KEY_API] = pub
        keys[DEV_KEY_SECRET] = priv
        # Insert into new file
        with open(DEV_KEY_FILE, 'w') as f:
            json.dump(keys, f, indent=4)
            print(f"Generated '{DEV_KEY_FILE}'")

    public_key = keys[DEV_KEY_API]
    private_key = keys[DEV_KEY_SECRET]

    assert args.wait != 0, "ERROR: must specify a non zero value for --wait, use 'python pymp.py -h' for help"
    pump_btc = float(args.btc)

    # create new client obj
    client = Client(public_key, private_key)
    client.API_URL = "https://testnet.binance.vision/api"  # test
    print("Session initiated with Binance API")

    # get BTC balance and assert there is enough in account
    btc_acc_amt = float(client.get_asset_balance(asset="BTC")['free'])
    assert btc_acc_amt >= pump_btc, "ERROR: insufficient BTC funds in account, specify a smaller value for --btc"

    # Wait for pump command
    coin = input("Ready. Awaiting coin symbol input: ").upper().strip() # pump coin
    symbol = f"{coin}BTC" # exchange symbol
    while client.get_symbol_info(symbol) is None:
        print("ERROR: inputted coin symbol is wrong!!!")
        coin = input("Re-enter coin symbol: ").upper().strip()
        symbol = f"{coin}BTC" # exchange symbol
    pump_buy_t0 = int(time.time() * 1000)  # ms
    pump_sell_t0 = pump_buy_t0 + args.wait * 1000  # time to sell at in ms

    # Place order at market value using a balance quote
    try:
        buy_order = client.create_test_order(symbol=symbol,
                                             side="BUY",
                                             type="MARKET",
                                             quantity=pump_btc) # change to create_order and use quoteOrderQty=
    except BinanceAPIException as e:
        # error handling goes here
        print(e)
    except BinanceOrderException as e:
        # error handling goes here
        print(e)
    # test buy case
    if "status" not in buy_order:
        print("TEST: order response is empty!")
        buy_order['status'] = 'FILLED'
        buy_order["transactTime"] = int(time.time() * 1000)
        buy_order["executedQty"] = 1
        buy_order['price'] = float(client.get_symbol_ticker(symbol="ETHBTC")['price'])
        # exit(0)
    # real buy case
    if buy_order["status"] == "FILLED":
        pump_buy_ms = buy_order["transactTime"] - pump_buy_t0 # Time taken to buy in ms
        executedQty = buy_order["executedQty"]
        buy_price = buy_order['price']
        print(f"Bought {executedQty} {coin} in {pump_buy_ms} ms for {buy_price} BTC per {coin}.")

        filled = True
    else:
        print(f"Order has not been filled. Response:")
        print(buy_order)
        exit(1)
    # bought successfully
    if filled:
        # initialise WebSocket for price polling
        bsm = BinanceSocketManager(client)
        conn_key = bsm.start_symbol_ticker_socket(symbol, update_price)
        # start the WebSocket
        bsm.start()
        sold = False
        pct_dev = 1  # deviation in percentage increase
        # sell either when percentage increase is reached or time delay is reached, whichever comes first
        while int(time.time() * 1000) < pump_sell_t0:
            with LIVE_PRICE_LOCK:
                if "last" not in live_price:
                    continue
                print(f"price for calc: {live_price['last']}")
                pct_increase = int((live_price['last'] - buy_price / buy_price) * 100)
                print(f"pct_increase: {pct_increase}")
            if (pct_increase + pct_dev >= args.pct) or (pct_increase - pct_dev >= args.pct):
                # percentage increase reached
                sell()
                sold = True
                break
        if not sold:
            # time delay reached
            sell()
            pass

        # stop websocket
        bsm.stop_socket(conn_key)
        reactor.stop()  # properly terminate WebSocket
    # normal exit
