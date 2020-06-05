from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager
import threading
import time
import json


class BinanceTickerReceiver:
    ask_price = None
    qty_in_best_ask = None

    bid_price = None
    qty_in_best_bid = None


    def __init__(self,):
        self.bm = BinanceWebSocketApiManager(exchange="binance.com-futures")
        def start_loop_for_ticker_receiving():
            while True:
                data = self.bm.pop_stream_data_from_stream_buffer()
                if not data:
                    time.sleep(0.1)
                try:
                    data = json.loads(data)
                    #print(data)
                    self.bid_price = float(data['data']['b'])
                    self.qty_in_best_bid = float(data['data']['B'])*self.bid_price # In USDT
                    self.ask_price = float(data['data']['a'])
                    self.qty_in_best_ask = float(data['data']['A'])*self.ask_price # In USDT
                except:
                    pass
                time.sleep(0.1)

        self.bm.create_stream({'bookTicker'}, {'ethusdt'})
        worker_thread = threading.Thread(target=start_loop_for_ticker_receiving)
        worker_thread.start()



    

    def stop(self):
        pass