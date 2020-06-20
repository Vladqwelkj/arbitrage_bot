import websocket
import json
import threading
import time

from bitmex_websocket import Instrument
from bitmex_websocket.constants import InstrumentChannels
from resources.utils import in_new_thread

class BitmexTickerReciever:
    ask_price = None
    qty_in_best_ask = None

    bid_price = None
    qty_in_best_bid = None

    def __init__(self):
        websocket.enableTrace(True)
        self.stream = Instrument(symbol='ETHUSD', channels=[InstrumentChannels.quote])
        self.stream.on('action', self._process_msg)
        worker_thread = threading.Thread(target=self.stream.run_forever)
        worker_thread.start()
        self._reconnect_in_23_hours()


    @in_new_thread
    def _reconnect_in_23_hours(self):
        timestamp_from_last_ws_starting = time.time()
        while True:
            if time.time() - timestamp_from_last_ws_starting > 23*60*60: #прошло 23 часа
                timestamp_from_last_ws_starting = time.time()
                self.stream.close()
                self.stream = Instrument(symbol='ETHUSD', channels=[InstrumentChannels.quote])
                self.stream.on('action', self._process_msg)
                worker_thread = threading.Thread(target=self.stream.run_forever)
                worker_thread.start()


    def _process_msg(self, msg):
        #print(msg)
        try:
            self.bid_price = msg['data'][0]['bidPrice']
            self.qty_in_best_bid = msg['data'][0]['bidSize']# In USD
            self.ask_price = msg['data'][0]['askPrice']
            self.qty_in_best_ask = msg['data'][0]['askSize']# In USD
        except:
            pass

