import os  # Util
import argparse  # Command parser
import time  # Timing
import json  # JSON

# python-binance lib
from binance.enums import *
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

DEV_KEY_FILE = "dev-key.json"  # dev key file
DEV_KEY_API = "api-key"  # api-key identifier
DEV_KEY_SECRET = "secret-key"  # secret-key identifier
TPS = 5  # ticks per second post-buy -> may also query binance at this rate


def input_keys():
    print("Please insert keys before usage.")
    pub = input("Enter public key: ").strip()
    priv = input("Enter private key: ").strip()

    return pub, priv


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
    pump_buy_t0 = int(round(time.time() * 1000))  # ms
    pump_sell_t0 = pump_buy_t0 + args.wait * 1000  # ms

    # Place order at market value using a balance quote
    with client.create_test_order(symbol=symbol,
                                  side="BUY",
                                  type="MARKET",
                                  quantity=pump_btc) as order: # change to create_order and use quoteOrderQty=
        if order["status"] == "FILLED":
            # TODO: Notify at which time the buy occurred
            pump_buy_ms = order["transactTime"] - pump_buy_t0 # Time taken to buy in ms
            executedQty = order["executedQty"]
            print(f"Bought {executedQty} {coin} in {pump_buy_ms} ms.")

            filled = True
        else:
            print(f"Order has not been filled. Response:")
            print(order)

    if filled:
        # Loop each tick at a TPS rate
        while int(round(time.time() * 1000)) < pump_sell_t0:
            pct_increase = 0 # TODO: Percentage monitoring
            if pct_increase >= args.pct:
                # Sell
                exit(0)

            time.sleep(1/TPS)

        # Sell as soon as either condition is reached
        # TODO: Execute sell
