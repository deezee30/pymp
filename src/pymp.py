import math
import os # Util
import argparse # Command parser
import time # Timing
import json # JSON
import threading  # multithreading

# python-binance lib
from binance.enums import *
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

# Constants
DEV_KEY_FILE = "dev-key.json" # dev key file
DEV_KEY_API = "api-key" # api-key identifier
DEV_KEY_SECRET = "secret-key" # secret-key identifier
QUOTE_ASSET = "BTC"
TPS = 5 # ticks per second post-buy -> may also query binance at this rate

# Realtime async price update
sync_lock = threading.Lock() # used for accessing sync price
order_last_price = None # last fetched order asset price
order_buy_price = None # order price at buy time

def prompt_key_file():
    """ Prompt to configure before usage, then quit 5s later. """

    print("Please insert keys before usage. Exiting in 5s...")
    time.sleep(5)
    exit()

def fetch_price(ping):
    """ Callback for updating last known quote asset price via web socket. """

    if ping["e"] != "error":
        with sync_lock:
            global order_last_price
            order_last_price = float(ping["c"])

def now():
    return int(round(time.time() * 1000)) # ms

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Pump n dump automated bot')
    parser.add_argument("--quote", type=str, default=None, required=True, help=f"amount of {QUOTE_ASSET} to use to purchase coin")
    parser.add_argument("--wait", type=int, default=0, required=True, help="Time to wait between buy and sell, in seconds")
    parser.add_argument("--sf", type=float, default=1., required=False, help="Sell factor: sf = sell price/buy price. Between 1.1 and 20")
    args = parser.parse_args()

    # Handle API key load
    if os.path.exists(DEV_KEY_FILE):
        # Load key file
        with open(DEV_KEY_FILE, 'r') as f:
            keys = json.loads(f.read())

        # Prompt to configure before usage
        if not keys[DEV_KEY_API] or not keys[DEV_KEY_SECRET]:
            prompt_key_file()
        
        public_key = keys[DEV_KEY_API]
        private_key = keys[DEV_KEY_SECRET]
    else:
        # Create blank keys
        keys = {
            DEV_KEY_API: "",
            DEV_KEY_SECRET: ""
        }

        # Insert into new file
        with open(DEV_KEY_FILE, 'w') as f:
            json.dump(keys, f, indent=4)
            print(f"Generated '{DEV_KEY_FILE}'")
        
        # Prompt to configure before usage
        prompt_key_file()

    assert args.wait != 0, "ERROR: Must specify a non zero value for --wait, use 'python pymp.py -h' for help"
    quote = float(args.quote)

    # Constrain sell factor within bounds if it's being used
    sf_crit = float(args.sf)
    if sf_crit < 1.1:
        sf_crit = 0
        print("Not using a sell factor")
    else:
        sf_crit = min(float(sf_crit), 20)
        print(f"Using a sell factor of {sf_crit}")

    # Create new client obj
    try:

        client = Client(public_key, private_key)
    except Exception as e:
        print(e)
        exit()
    print("Session initiated with Binance API")
    
    # Ensure the balance of the quote asset is large enough for purchase.
    quote_bal = float(client.get_asset_balance(asset=QUOTE_ASSET)['free'])
    if quote_bal < quote:
        print(f"Error: Insufficient {QUOTE_ASSET} ({quote_bal} < {quote})")
        exit()

    # Obtain a list of available coins for quote asset prematurely. This is done to avoid sending additional
    # queries after pump command in order to speed up buying time.
    assets = [sym["baseAsset"] for sym in client.get_exchange_info()["symbols"]
                              if sym["quoteAsset"] == QUOTE_ASSET]

    # Wait for pump command
    base_asset = input("Ready. Awaiting coin input (Base asset): ").strip().upper() # pump coin
    
    # Only accept valid coins
    while base_asset not in assets:
        base_asset = input(f"Coin ${base_asset} does not exist. Try again: ").strip().upper() # pump coin
    
    symbol = f"{base_asset}{QUOTE_ASSET}" # exchange symbol

    # Timings
    pump_buy_t0 = now() # ms
    pump_sell_t0 = pump_buy_t0 + (args.wait-1) * 1000 # ms

    buy_filled = False

    # Place order at market value using a balance quote
    try:
        order = client.order_market_buy(symbol=symbol,
                                        newOrderRespType=ORDER_RESP_TYPE_FULL,
                                        quoteOrderQty=quote)
        if order["status"] == "FILLED":
            fills = order["fills"]
            fills_num = len(fills)

            executedQty = float(order["executedQty"])
            order_buy = sum(float(fill["price"]) * float(fill["qty"]) for fill in fills)
            order_buy_price = order_buy / executedQty

            pump_buy_t1 = order["transactTime"]
            pump_buy_ms = pump_buy_t1 - pump_buy_t0 # Time taken to buy in ms
            
            s, ms = divmod(pump_buy_t1, 1000)

            print("Bought {qty} {base} for {price} {asset} in {time} ms ({fills} fills @ {timestamp}.{ms:03d})".format(
                qty=executedQty, base=base_asset, price=order_buy,
                asset=QUOTE_ASSET, time=pump_buy_ms, fills=fills_num,
                timestamp=time.strftime('%H:%M:%S', time.gmtime(s)), ms=ms))

            buy_filled = True
        else:
            print(f"Order has not been filled. Response:")
            print(order)
    except BinanceAPIException as e:
        # error handling goes here
        print(e)
    except BinanceOrderException as e:
        # error handling goes here
        print(e)
    finally:
        pass
    
    if buy_filled:
        # Init and start the WebSocket
        bsm = BinanceSocketManager(client)
        # Schedule a price update
        conn_key = bsm.start_symbol_ticker_socket(symbol, fetch_price)
        bsm.start()

        symbol_info = client.get_symbol_info(symbol)

        # ensure LOT_SIZE constraint passes
        step_size = float(symbol_info['filters'][2]['stepSize'])
        base_bal = float(client.get_asset_balance(asset=base_asset)['free'])
        sell_qty = float(math.floor(base_bal * (1/step_size))) / (1/step_size)

        # Loop each tick at a TPS rate
        while (update := now()) < pump_sell_t0:

#            # Update on progress
#            if ((update - pump_buy_t1) / (args.wait * 1000)) % 10 < 1000:
#                print("=", end="")

            # If sell factor triggering is enabled, schedule a price update
            # and monitor the sell factor increase
            if order_last_price and sf_crit != 0:
                
                # Monitor the sell factor increase
                with sync_lock:
                    sf = order_last_price / order_buy_price
                    if sf >= sf_crit:
                        break

            time.sleep(1/TPS)
        
        pump_sell_t0 = int(round(time.time() * 1000)) # ms
        
        # Sell as soon as either condition is reached
        try:
            order = client.order_market_sell(symbol=symbol,
                                             newOrderRespType=ORDER_RESP_TYPE_FULL,
                                             quantity=sell_qty)
            if order["status"] == "FILLED":
                fills = order["fills"]
                fills_num = len(fills)

                executedQty = float(order["executedQty"])
                sell = sum(float(fill["price"]) * float(fill["qty"]) for fill in fills)
                sell_price = sell / executedQty

                pump_sell_t1 = order["transactTime"]
                pump_sell_ms = pump_sell_t1 - pump_sell_t0 # Time taken to buy in ms
                
                s, ms = divmod(pump_sell_t1, 1000)

                print("Sold {qty} {base} for {price} {asset} in {time} ms ({fills} fills @ {timestamp}.{ms:03d})".format(
                    qty=executedQty, base=base_asset, price=sell,
                    asset=QUOTE_ASSET, time=pump_sell_ms, fills=fills_num,
                    timestamp=time.strftime('%H:%M:%S', time.gmtime(s)), ms=ms))
                
                print("Profit: {:.4f}%".format(100 * (sell - order_buy) / order_buy))

                sell_filled = True
            else:
                print(f"Order has not been filled. Response:")
                print(order)
        except BinanceAPIException as e:
            # error handling goes here
            print(e)
        except BinanceOrderException as e:
            # error handling goes here
            print(e)
        finally:
            pass
        
        # stop websocket
        bsm.stop_socket(conn_key)

        # properly terminate WebSocket
        reactor.stop()