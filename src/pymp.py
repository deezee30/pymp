import os
import argparse
from binance.enums import *
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Pump n dump automated bot')
    parser.add_argument("--public_key", type=str, default=None, required=True, help="Binance user API public key")
    parser.add_argument("--private_key", type=str, default=None, required=True, help="Binance user API private key")
    parser.add_argument("--btc", type=str, default=None, required=True, help="amount of BTC to use to purchase SHT")
    parser.add_argument("--timer", type=int, default=0, required=True, help="Time to wait between buy and sell, in seconds")
    parser.add_argument("--percentage", type=int, default=0, required=True, help="Percentage increase from buy price at which to sell")
    args = parser.parse_args()

    assert args.timer != 0, "ERROR: must specify a non zero value for --timer, use 'python pumpndump.py -h' for help"
    btc = float(args.btc)

    # create new client obj
    client = Client(args.public_key, args.private_key)

    # change API endpoint for testing
    # client.API_URL = "https://testnet.binance.vision/api"

    # get BTC balance and assert there is enough in account
    btc_acc_amt = float(client.get_asset_balance(asset="BTC")['free'])
    assert btc_acc_amt >= btc, "ERROR: insufficient BTC funds in account, specify a smaller value for --btc"

    # Mode 1 (timer only)
    # sell after specified time
    if args.percentage == 0:
        pass

    # Mode 2 (percentage/timer combo)
    # sell if the inputted percentage increase or timer value is reached, whichever comes first
    else:
        pass



