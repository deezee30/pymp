import os
import argparse
from decimal import Decimal
from binance.enums import *
from binance.client import Client
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Pump n dump automated bot')
    parser.add_argument("--public_key", type=str, default=None, required=True, help="Binance user API public key")
    parser.add_argument("--private_key", type=str, default=None, required=True, help="Binance user API private key")
    parser.add_argument("--altcoin", type=str, default=None, required=True, help="the altcoin symbol (SHT) to buy with BTC")
    parser.add_argument("--btc_amt", type=str, default=None, required=True, help="amount of BTC (max 8 decimal places) to use to purchase SHT")
    parser.add_argument("--timer", type=int, default=0, required=True, help="Time to wait between buy and sell, in seconds")
    parser.add_argument("--percentage", type=int, default=0, required=True, help="Percentage increase from buy price at which to sell")
    args = parser.parse_args()

    assert args.timer != 0, "ERROR: must specify a non zero value for --timer, use 'python pumpndump.py -h' for help"

    # test API keys and client
    test_api = "SPeY1nXjquzNpTNt8Iz1Wd3liuXVxLqNS1Zlwy6KAZl5XrwMQeLMvvzZEVrIX0ZT"
    test_secret = "FMZZ8y8BBMuukqHG1VzInt2gAYKchqBowgLgZh0EQAf5UMgSYH2H2JzgPQYlOdDA"
    client = Client(test_api, test_secret)  # test
    client.API_URL = "https://testnet.binance.vision/api" # test

    # create new client obj
    # client = Client(args.public_key, args.private_key)
    trade_pair = args.altcoin+"BTC"
    assert client.get_symbol_info(trade_pair) is not None, "ERROR: altcoin symbol is incorrect"

    # get BTC balance and assert there is enough in account
    btc_acc_amt = float(client.get_asset_balance(asset="BTC")['free'])
    assert btc_acc_amt >= float(args.btc_amt), "ERROR: insufficient BTC funds in account, specify a smaller value for --btc"

    # Mode 1 (timer only)
    # sell after specified time
    if args.percentage == 0:
        buy_market = client.create_test_order(symbol=trade_pair,
                                              side="BUY",
                                              type="MARKET",
                                              quantity=args.btc_amt)
        pass

    # Mode 2 (percentage/timer combo)
    # sell if the inputted percentage increase or timer value is reached, whichever comes first
    else:
        pass



