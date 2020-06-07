#from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager
from resources.binance_futures.binance_futures import WebsocketMarket
import threading
import time
import json


class BinanceTickerReceiver:
    ask_price = None
    qty_in_best_ask = None

    bid_price = None
    qty_in_best_bid = None


    def __init__(self,):
        def process_message(ws, msg):
            print(msg)
            try:
                self.ask_price = float(msg['a'][0][0])
                self.bid_price = float(msg['b'][0][0])
                self.qty_in_best_ask = float(msg['a'][0][1])*self.ask_price
                self.qty_in_best_bid = float(msg['b'][0][1])*self.bid_price
            except Exception as er:
                print('ws price binance error: ', str(er))
        WebsocketMarket(symbol='ethusdt', on_message=process_message, speed='100ms').partial_book_depth_socket(levels=5)



    

    def stop(self):
        pass
