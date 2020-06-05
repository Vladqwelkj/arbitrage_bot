import websocket
import json
import threading
import time

from bitmex_websocket import Instrument
from bitmex_websocket.constants import InstrumentChannels

class BitmexTickerReciever:
    ask_price = None
    qty_in_best_ask = None

    bid_price = None
    qty_in_best_bid = None

    def __init__(self):
        websocket.enableTrace(True)

        def process_msg(msg):
            #print(msg)
            try:
                self.bid_price = msg['data'][0]['bidPrice']
                self.qty_in_best_bid = msg['data'][0]['bidSize']# In USD
                self.ask_price = msg['data'][0]['askPrice']
                self.qty_in_best_ask = msg['data'][0]['askSize']# In USD
            except:
                pass

        stream = Instrument(symbol='ETHUSD', channels=[InstrumentChannels.quote])
        stream.on('action', process_msg)
        worker_thread = threading.Thread(target=stream.run_forever)
        worker_thread.start()
