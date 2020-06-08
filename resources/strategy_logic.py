from datetime import datetime
from dateutil import tz
import time
import requests
import threading

from resources.utils import in_new_thread
from resources.log_record import LogRecord

TIMEZONE_FOR_LOG = 'Europe/Moscow'

class Strategy:
    spread_records = []
    spread_recorder_is_available = True
    web_log_records = []
    all_position_qty_filled = False
    now_in_position = False
    remain_qty_for_position = 0
    reversed_position = False # reverse when long binance and short bitmex

    def __init__(self,
        binance_client,
        binance_ticker_receiver,
        bitmex_client,
        bitmex_ticker_receiver,
        email_client,
        amount_to_trade_percent=100,
        bottom_spread=-0.4,
        top_spread=0.6,
        #second_enter=-0.05,
        warning_diff_percent=10, #  Для отправки разницы на почту
        ):
        
        self.binance_client = binance_client
        self.binance_ticker_receiver = binance_ticker_receiver
        self.bitmex_client = bitmex_client
        self.bitmex_ticker_receiver = bitmex_ticker_receiver
        self.amount_to_trade_percent = amount_to_trade_percent
        self.bottom_spread = bottom_spread
        self.top_spread = top_spread
        self.email_client = email_client
       # self.second_enter = second_enter
        self.warning_diff_percent = warning_diff_percent #  Для отправки разницы на почту


    @in_new_thread
    def start(self):
        self.ON = True
        self._record_in_log('Начало работы')
        time.sleep(6)
        self._close_positions()
        while self.ON:
            time.sleep(0.7)
            spread = self.bitmex_ticker_receiver.ask_price - self.binance_ticker_receiver.bid_price
            print(self.bitmex_ticker_receiver.ask_price, self.binance_ticker_receiver.bid_price)
            self._record_spread(spread)
            if spread <= self.bottom_spread: # short binance, long bitmex
                if self.now_in_position and self.reversed_position:
                    self._close_positions()
                    continue
                self._make_deal(long_bitmex_and_short_binance=True)
                self.reversed_position = False
            if self.bitmex_ticker_receiver.bid_price - self.binance_ticker_receiver.ask_price >= self.top_spread:
                if self.now_in_position and not self.reversed_position:
                    self._close_positions()
                    continue
                self.reversed_position = True
                self._make_deal(short_bitmex_and_long_binance=True)
            print(spread, self.bitmex_ticker_receiver.bid_price - self.binance_ticker_receiver.ask_price)




    def _make_deal(self, long_bitmex_and_short_binance=False, short_bitmex_and_long_binance=False):
        if long_bitmex_and_short_binance and short_bitmex_and_long_binance:
            print('Невозможна односторонняя позиция на обоих бержах')
            return False
        if self.now_in_position and self.all_position_qty_filled:
            return
        if not self.all_position_qty_filled:
            self._record_in_log(
                'Bitmex: {}, Binance: {}, разница: {}. Начинаем {} на Binance и {} на Bitmex'.format(
                    self.bitmex_ticker_receiver.ask_price,
                    self.binance_ticker_receiver.bid_price,
                    round(self.bitmex_ticker_receiver.ask_price-self.binance_ticker_receiver.bid_price, 3),
                    'продавать' if long_bitmex_and_short_binance else 'покупать',
                    'продавать' if short_bitmex_and_long_binance else 'покупать',
                    ))

            # amount to trade processing:
            available_qty_in_orderbook = min( # in USD
                self.bitmex_ticker_receiver.qty_in_best_ask,
                self.binance_ticker_receiver.qty_in_best_bid)
            ideal_amount_to_trade = self._calc_amount_for_trade()
            if ideal_amount_to_trade < available_qty_in_orderbook:
                amount_to_trade = ideal_amount_to_trade
                self.all_position_qty_filled = True
                self._record_in_log('В стакане достаточно средств для позиции в {}$'.format(amount_to_trade))
            else:
                amount_to_trade = available_qty_in_orderbook
                self.remain_qty_for_position = ideal_amount_to_trade - amount_to_trade
                self._record_in_log('В стакане не хватает средств для всей сделки({}$). Используем только {}$'.format(
                    ideal_amount_to_trade, amount_to_trade))
            if self.remain_qty_for_position < 2 and self.now_in_position:
                self.all_position_qty_filled = True
                return

            #trading:
            self._market_order_binance(False if long_bitmex_and_short_binance else True, amount_to_trade/self.binance_ticker_receiver.bid_price,)
            self._market_order_bitmex(True if long_bitmex_and_short_binance else False, amount_to_trade)
            self.now_in_position = True



    @in_new_thread
    def _market_order_binance(self, side_is_buy, qty_in_eth):
       # print(9191919199)
        qty = round(abs(float(qty_in_eth)), 3)
        order = self.binance_client.new_order(
            side='BUY' if side_is_buy else 'SELL',
            quantity=(qty),
            orderType='MARKET',)
        self._record_in_log('Binance: выставлен ордер на {} на {}'.format(
            'покупку' if side_is_buy else 'продажу',
            qty),
            color='green' if side_is_buy else 'red',)
        return order



    @in_new_thread
    def _market_order_bitmex(self, side_is_buy, qty):
        print('bitmex qty:', round(abs(float(qty))))
        for n_errors in range(1, 6): #5 попыток
            try:
                order = self.bitmex_client.Order.Order_new( #Market
                   symbol = 'ETHUSD',
                   side = 'Buy' if side_is_buy else 'Sell',
                   orderQty = round(abs(float(qty))),
                   ).result()
                self._record_in_log('Bitmex: выставлен ордер на {} на {}$'.format(
                    'покупку' if side_is_buy else 'продажу',
                    round(qty)),
                    color='green' if side_is_buy else 'red',)
                return order
            except Exception as er:
                print('bitmex error order placing:', str(er))
                self._record_in_log(
                    'Ошибка выставления ордера на Bitmex. Повтор через 5 секунд. Попытка №'+str(n_errors))
                time.sleep(5.5)






    def _close_positions(self):
        self.now_in_position = False
        qty_for_binance = -self._get_binance_position_amount()['ETH']
        qty_for_bitmex = -self._get_bitmex_position_amount()['USD']
        if not qty_for_binance==0 or qty_for_bitmex==0:
            # процесс закрытия позиций
            self._record_in_log('Закрытие позиций. На Bitmex: {}$, на Binance {} ETH'.format(
                qty_for_bitmex, qty_for_binance))
            binance_closing_position = threading.Thread(
                target=self._market_order_binance,
                args=(True if qty_for_binance>0 else False, qty_for_binance,))
            bitmex_closing_position = threading.Thread(
                target=self._market_order_bitmex,
                args=(True if qty_for_bitmex>0 else False, qty_for_bitmex,))

            binance_closing_position.start()
            bitmex_closing_position.start()
            binance_closing_position.join()
            bitmex_closing_position.join()
        self.all_position_qty_filled = False
        bitmex_balance = self._get_bitmex_balance_in_usd()
        binance_balance = self._get_binance_balance_in_usd()
        if bitmex_balance/binance_balance > 1+(self.warning_diff_percent/100):
            self.email_client.send_notification_about_balance(
                bitmex_balance=bitmex_balance,
                binance_balance=binance_balance)
        


    def _calc_amount_for_trade(self): # In USD
        amount = self._get_bitmex_balance_in_usd()*(self.amount_to_trade_percent/100)
        return amount


    def _get_binance_position_amount(self):
        ETHUSDT_price = self.binance_ticker_receiver.bid_price
        for asset in self.binance_client.position_info():
            if asset['symbol']=='ETHUSDT':
                return {
                    'ETH': float(asset['positionAmt']),
                    'USD': float(asset['positionAmt'])*ETHUSDT_price,
                    }



    def _get_bitmex_position_amount(self):
        for n_error in range(5):
            try:
                for asset in self.bitmex_client.Position.Position_get().result()[0]:
                    if asset['symbol']=='ETHUSD':
                        return {'USD': int(asset['execQty']),}
                        break
                return
            except Exception as er:
                print('Ошибка при получении баланса Bitmex, попытка через 5 сек:', str(er))
                time.sleep(5.5)



    def _get_bitmex_balance_in_usd(self):
        for n_errors in range(1, 6):
            try:
                balance_btc = self.bitmex_client.User.User_getMargin(
                    currency='XBt'
                    ).result()[0]['amount']/(10**8)
                balance_usd = balance_btc*self._get_XBTUSD_price()
                return balance_usd
            except Exception as er:
                print('Ошибка при получени баланса bitmex:', str(er))
                time.sleep(5.5)

    def _get_binance_balance_in_usd(self):
        return float(self.binance_client.balance()[0]['balance'])


    def _get_XBTUSD_price(self): #from bitmex
        price = requests.get('https://www.bitmex.com/api/v1/orderBook/L2?symbol=XBTUSD&depth=1').json()[0]['price']
        return price



    @in_new_thread
    def _record_spread(self, spread):
        if self.spread_recorder_is_available:
            self.spread_recorder_is_available = False
            self.spread_records.append((datetime.now().astimezone(tz.gettz(TIMEZONE_FOR_LOG)), round(spread, 3)))
            if len(self.spread_records) > 1440*7*4: # Записей больше, чем минут в неделе
                del self.spread_records[0] #удалить первую запись
            time.sleep(15)
            self.spread_recorder_is_available = True

    def _record_in_log(self, text, color='black'):
        dt = datetime.now().astimezone(tz.gettz(TIMEZONE_FOR_LOG))
        text_to_print = '/n[{}:{}:{}] {}'.format(dt.hour, dt.minute, dt.second, text)
        print(text_to_print)
        open('log.log', 'a').write(text)
        self.web_log_records.append(LogRecord(dt=dt, text=text, color=color))


    def stop(self):
        self.ON = False
