import os  # OS Util funcs
import time  # Timing
import json  # JSON
import math  # math utils funcs
import argparse  # Command parser
import threading  # multithreading

# python-binance lib
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

# keys
TEST_DEV_KEY_FILE = "test-dev-key.json"  # test framework keys
DEV_KEY_FILE = "dev-key.json"  # dev key file
DEV_KEY_API = "api-key"  # api-key identifier
DEV_KEY_SECRET = "secret-key"  # secret-key identifier

# GLOBAL
# set up parameters for websocket
cur_price = 0  # initialise most recent price returned by websocket to some value
pct_dev = 1.0  # deviation in percentage increase
# set up extra parameters
sold = False
timer_transaction = None


def get_keys(test=False):
    """
        Handle API keys load

        :input: test flag

        :return: public key string, private key string
    """
    global DEV_KEY_FILE
    if test:
        DEV_KEY_FILE = TEST_DEV_KEY_FILE
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

    return keys[DEV_KEY_API], keys[DEV_KEY_SECRET]


def input_keys():
    """
    prompt user to enter their Binance API public and private keys

    :return: public key string, private key string
    """
    print("Binance API user keys either incomplete or not found.\nPlease insert your keys before usage.")
    pub = input("Enter public key:").strip()
    priv = input("Enter private key:").strip()

    return pub, priv


def update_price(msg):
    """
        callback function

        process incoming WebSocket price update for SHT/BTC trades:
            - calculate the percentage increase from the buy price
            - sell if percentage increase above args.pct
    """
    global sold, cur_price, pct_dev
    if not sold:
        if msg['e'] != 'error':
            new_price = float(msg['c'])  # current price
            print(f"new price: {new_price}")
            if new_price == cur_price:
                return  # new trade had the same price as previous trade
            print(f"price for calc: {new_price}")
            pct_increase = ((new_price - buy_price) / buy_price) * 100.0
            print(f"pct_increase: {pct_increase}")
            if (pct_increase + pct_dev >= pct) or (pct_increase - pct_dev >= pct):
                # percentage increase reached
                sell("percentage increase reached")
                return
            cur_price = new_price


def sell(reason):
    """
        sell all SHT coins in wallet for BTC

        set sold flag to true
        cancel the timer
    """
    global sold, timer_transaction
    if sold:
        return

    # ensure LOT_SIZE constraint passes
    step_size = float(symbol_info['filters'][2]['stepSize'])
    coin_amt = float(client.get_asset_balance(asset=coin)['free'])
    coin_amt = float(math.floor(coin_amt * (1/step_size))) / (1/step_size)

    pump_sell_t1 = int(time.time() * 1000)  # ms

    try:
        sell_order = client.create_order(symbol=symbol,
                                         side="SELL",
                                         type="MARKET",
                                         quantity=coin_amt)
        with open("sell-order-response.json", 'w') as f:
            json.dump(sell_order, f, indent=4)
            print(f"Generated sell-order-response.json")
    except BinanceAPIException as e:
        print(e)
    except BinanceOrderException as e:
        print(e)

    if 'sell_order' in locals() and sell_order["status"] == "FILLED":
        pump_sell_ms = sell_order["transactTime"] - pump_sell_t1  # Time taken to sell in ms
        executedQty = sell_order["executedQty"]
        sell_price = sum([float(fill['qty']) * float(fill['price']) for fill in sell_order['fills']])
        print(f"Sold {executedQty} {coin} in {pump_sell_ms} ms for {sell_price} BTC due to {reason}.")
        sold = True
        if timer_transaction is not None:
            timer_transaction.cancel()
    else:
        print(f"Order has not been filled. Response:")
        print(sell_order)
        exit(1)


if __name__ == "__main__":
    # parse program arguments
    parser = argparse.ArgumentParser(description='Pump n dump automated bot')
    parser.add_argument("--btc", type=str, default=None, required=True, help="amount of BTC to use to purchase coin")
    parser.add_argument("--wait", type=int, default=0, required=True,
                        help="Time to wait between buy and sell, in seconds")
    parser.add_argument("--pct", type=str, default='10000.0', required=False,
                        help="Percentage increase from buy price at which to sell")
    args = parser.parse_args()

    # get public and private keys
    public_key, private_key = get_keys(test=False)

    # ensure wait arg is specified with a non zero value
    assert args.wait != 0, "ERROR: must specify a non zero value for --wait, use 'python pymp.py -h' for help"
    pct = float(args.pct)
    pump_btc = float(args.btc)

    # create new client obj
    client = Client(public_key, private_key)
    print("Session initiated with Binance API")
    # client.API_URL = "https://testnet.binance.vision/api"  # for testing

    # get BTC balance and assert there is enough in account
    btc_acc_amt = round(float(client.get_asset_balance(asset="BTC")['free']), 8)
    assert btc_acc_amt >= pump_btc, "ERROR: insufficient BTC funds in account, specify a smaller value for --btc"

    # Wait for pump command
    coin = input("Ready. Awaiting coin symbol input:").upper().strip()  # pump coin
    symbol = f"{coin}BTC"  # exchange symbol
    while client.get_symbol_info(symbol) is None:
        print("ERROR: inputted coin symbol is wrong!!!")
        coin = input("Re-enter coin symbol:").upper().strip()
        symbol = f"{coin}BTC"  # exchange symbol
    symbol_info = client.get_symbol_info(symbol)

    # debug
    with open("symbol-info-response.json", 'w') as f:
        json.dump(symbol_info, f, indent=4)
        print(f"Generated symbol-info-response.json")

    # buy time in ms
    pump_buy_t0 = int(time.time() * 1000)

    # Place order at market value using a balance quote
    try:
        buy_order = client.create_order(symbol=symbol,
                                        side="BUY",
                                        type="MARKET",
                                        quoteOrderQty=pump_btc)  # change to create_order and use quoteOrderQty=
        with open("buy-order-response.json", 'w') as f:
            json.dump(buy_order, f, indent=4)
            print(f"Generated buy-order-response.json")
    except BinanceAPIException as e:
        print(e)
    except BinanceOrderException as e:
        print(e)
    # real buy case
    if 'buy_order' in locals() and buy_order["status"] == "FILLED":
        pump_buy_ms = buy_order["transactTime"] - pump_buy_t0  # Time taken to buy in ms
        executedQty = buy_order["executedQty"]
        # get weighted average buy price for order
        total_qty = sum([float(fill['qty']) for fill in buy_order['fills']])
        buy_price = round(sum([float(fill['qty']) * float(fill['price']) for fill in buy_order['fills']]) / total_qty, 8)
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

        # sell either when percentage increase is reached or time delay is reached, whichever comes first
        timer_transaction = threading.Timer(args.wait, sell, ["timer expiry"])
        timer_transaction.start()
        timer_transaction.join()

        # stop websocket
        bsm.stop_socket(conn_key)
        reactor.stop()  # properly terminate WebSocket
