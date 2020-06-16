from datetime import datetime
from dateutil import tz
import time
import requests
import threading

from resources.utils import in_new_thread
from resources.log_record import LogRecord

TIMEZONE_FOR_LOG = 'Europe/Moscow'

class Strategy:
    spread_records = [(int(time.time()), 0,0,0,0), ]
    spread_recorder_is_need_to_close = True
    spreads_tmp = []
    balance_bitmex_start = 0
    balance_binance_start = 0
    web_log_records = []
    PnL_history = []
    bitmex_binance_balances_history = [] # unixtime, bitmex, binance
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
        self.clear_web_log()
        self._record_in_log('Начало работы')
        time.sleep(6)
        self._close_positions(calc_profit=False)
        self._print_balances()
        self._calc_initial_balances()
        while self.ON:
            time.sleep(0.7)

            if self.check_spread_condition(): # short binance, long bitmex
                if self.now_in_position and self.reversed_position:
                    self._close_positions()
                    continue
                self._make_deal(long_bitmex_and_short_binance=True)
                self.reversed_position = False
            if self.check_spread_condition(for_reverse_deal=True):
                if self.now_in_position and not self.reversed_position:
                    self._close_positions()
                    continue
                self.reversed_position = True
                self._make_deal(short_bitmex_and_long_binance=True)
            print(spread, self.bitmex_ticker_receiver.bid_price - self.binance_ticker_receiver.ask_price)


    def check_spread_condition(self, for_reverse_deal=False):
        spread = self.bitmex_ticker_receiver.ask_price - self.binance_ticker_receiver.bid_price
        spread_for_reverse = self.bitmex_ticker_receiver.bid_price - self.binance_ticker_receiver.ask_price
        self._record_spread(spread)
        if not for_reverse_deal and spread <= self.bottom_spread:
            return True
        if for_reverse_deal and spread_for_reverse >= self.top_spread:
            return True
        else:
            return False
            



    def _make_deal(self, long_bitmex_and_short_binance=False, short_bitmex_and_long_binance=False):
            #trading:
            while True:
                if long_bitmex_and_short_binance:
                    price = bitmex_ticker_receiver.ask_price
                    side_is_buy = True
                if short_bitmex_and_long_binance:
                    price = bitmex_ticker_receiver.bid_price
                    side_is_buy = False

                if self.check_spread_condition() or self.check_spread_condition(for_reverse_deal=True):
                    if long_bitmex_and_short_binance and short_bitmex_and_long_binance:
                        return
                    if self.now_in_position and self.all_position_qty_filled:
                        return
                    if not self.all_position_qty_filled:
                        self._record_in_log(
                            'Bitmex: {}, Binance: {}, спред: {}. Начинаем {} на Binance и {} на Bitmex'.format(
                                self.bitmex_ticker_receiver.ask_price,
                                self.binance_ticker_receiver.bid_price,
                                round(self.bitmex_ticker_receiver.ask_price-self.binance_ticker_receiver.bid_price, 3),
                                'продавать' if long_bitmex_and_short_binance else 'покупать',
                                'продавать' if short_bitmex_and_long_binance else 'покупать',
                                ))

                        # amount to trade calculating:
                        available_qty_in_orderbook = min( # in USD
                            self.bitmex_ticker_receiver.qty_in_best_ask,
                            self.binance_ticker_receiver.qty_in_best_bid)
                        if not self.now_in_position:
                            ideal_amount_to_trade = self._calc_amount_for_trade()
                            self.remain_qty_for_position = ideal_amount_to_trade
                        if self.remain_qty_for_position < 2 and self.now_in_position:
                            self.all_position_qty_filled = True
                            return
                        if self.remain_qty_for_position < available_qty_in_orderbook:
                            amount_to_trade = self.remain_qty_for_position 
                            self.remain_qty_for_position = 0
                            self.all_position_qty_filled = True
                            self._record_in_log('В стакане достаточно средств для позиции в {}$'.format(amount_to_trade))
                        else:
                            amount_to_trade = available_qty_in_orderbook
                            self.remain_qty_for_position -= amount_to_trade
                            self._record_in_log('В стакане не хватает средств для всей сделки({}$). Используем только {}$'.format(
                                self.remain_qty_for_position, amount_to_trade))

                    # order placing:
                    order_bitmex = self._limit_order_bitmex(side_is_buy, amount_to_trade, price)
                    if order_bitmex[0]['ordStatus']=='New':
                        break
                else:
                    return

            time_from_order_placing = time.time()
            while True: # Слежение за тем, чтобы получить позицию
                if self._get_order_bitmex_status_by_id(order_bitmex[0]['orderID'])=='Filled':
                    self._record_in_log('Лимитный ордер на bitmex заполнен')
                    break
                if time.time() - time_from_order_placing > 60*7: # не исполняется больше X минут.
                    self._record_in_log(
                        'Не можем зайти в позицию на bitmex в течении нескольких минут. Отмена сделки')
                    self._cancel_bitmex_order_by_id(order_bitmex[0]['orderID'])
                    self._close_positions(calc_profit=False)
                    return
                if (not self.check_spread_condition()) and (not self.check_spread_condition(for_reverse_deal=True)): # спред больше не подходит для сделки
                    self._record_in_log('Пока ожидали исполнение ордера на bitmex, размер спред перестал быть нужным. Отмена сделки')
                    self._cancel_bitmex_order_by_id(order_bitmex[0]['orderID'])
                    self._close_positions(calc_profit=False)
                    return
                time.sleep(2.5)

            # Когда исполнен ордер на битмиксе, исполнить маркет на бинансе
            self._market_order_binance(False if long_bitmex_and_short_binance else True, amount_to_trade/self.binance_ticker_receiver.bid_price,)
            self.now_in_position = True



    @in_new_thread
    def _market_order_binance(self, side_is_buy, qty_in_eth):
        if qty_in_eth==0:
            return
        qty = round(abs(float(qty_in_eth)), 3)
        order = self.binance_client.new_order(
            side='BUY' if side_is_buy else 'SELL',
            quantity=(qty),
            orderType='MARKET',)
        self._record_in_log('Binance: выставлен ордер на {} на {} по ~{}'.format(
            'покупку' if side_is_buy else 'продажу',
            qty,
            order['avgPrice']),
                color='green' if side_is_buy else 'red',)
        return order



    #@in_new_thread
    def _market_order_bitmex(self, side_is_buy, qty):
        if qty==0:
            return
        print('bitmex qty:', round(abs(float(qty))))
        for n_errors in range(1, 7): #6 попыток
            try:
                order = self.bitmex_client.Order.Order_new( #Market
                   symbol = 'ETHUSD',
                   side = 'Buy' if side_is_buy else 'Sell',
                   orderQty = round(abs(float(qty))),
                   ).result()
                self._record_in_log('Bitmex: выставлен ордер на {} на {}$ по ~{}'.format(
                    'покупку' if side_is_buy else 'продажу',
                    round(qty),
                    order[0]['avgPx']),
                        color='green' if side_is_buy else 'red',)
                return order
            except Exception as er:
                self._record_in_log('bitmex error order placing:'+str(er))
                self._record_in_log(
                    'Ошибка выставления ордера на Bitmex. Повтор через 5 секунд. Попытка №'+str(n_errors))
                time.sleep(5)


    def _limit_order_bitmex(self, side_is_buy, qty, price):
        if qty==0:
            return
        for n_errors in range(1, 7): #6 попыток
            try:
                order = self.bitmex_client.Order.Order_new( #Market
                    ordType='Limit',
                    price=price,
                   symbol = 'ETHUSD',
                   side = 'Buy' if side_is_buy else 'Sell',
                   orderQty = abs(int(qty)),
                   execInst='ParticipateDoNotInitiate',
                   ).result()
                self._record_in_log('Bitmex: выставлен limit ордер на {} на {}$ по ~{}'.format(
                    'покупку' if side_is_buy else 'продажу',
                    round(qty),
                    price,),
                        color='green' if side_is_buy else 'red',)
                return order
            except Exception as er:
                self._record_in_log('bitmex error order placing:'+str(er))
                self._record_in_log(
                    'Ошибка выставления ордера на Bitmex. Повтор через 5 секунд. Попытка №'+str(n_errors))
                time.sleep(5)



    def _get_order_bitmex_status_by_id(self, order_id):
        for n_errors in range(1, 6): #5 попыток
            try:
                orders = self.bitmex_client.Order.Order_getOrders(symbol='ETHUSD').result()[0]
                break
            except Exception as e:
                print('Ошибка при получении статуса ордера: ', str(e))
                time.sleep(5.5)
        for order in orders:
            if order['orderID']==orderID:
                return order['ordStatus']



    def _cancel_bitmex_order_by_id(self, order_id):
        for n_errors in range(1, 6): #5 попыток
            try:
                self.bitmex_client.Order.Order_cancel(orderID=order_id).result()
                self._record_in_log('Успешно удален ордер '+str(order_id))
                return
            except Exception as e:
                print('Ошибка при удалении ордера: ', str(e))
                time.sleep(5.5)



    def _close_positions(self, calc_profit=True):
        self.now_in_position = False
        btimex_position_info = self._get_binance_position_amount()
        qty_for_binance = abs(btimex_position_info['ETH'])
        qty_for_bitmex = -self._get_bitmex_position_amount()['USD']
        if not (qty_for_binance==0 and qty_for_bitmex==0):
            # процесс закрытия позиций
            self._record_in_log('Закрытие позиций. На Bitmex: {}$, на Binance {} ETH. Спред: {}'.format(
                qty_for_bitmex,
                qty_for_binance,
                self.bitmex_ticker_receiver.ask_price - self.binance_ticker_receiver.bid_price))
            binance_closing_position = threading.Thread(
                target=self._market_order_binance,
                args=(True if qty_for_binance>0 else False, qty_for_binance,))
            bitmex_closing_position = threading.Thread(
                target=self._market_order_bitmex,
                args=(True if qty_for_bitmex>0 else False, qty_for_bitmex,))

            bitmex_closing_position.start()
            bitmex_closing_position.join()
            binance_closing_position.start()
            binance_closing_position.join()
            
        self.all_position_qty_filled = False
        bitmex_balance_btc = self._get_bitmex_balance_in_btc()
        bitmex_balance = self._get_bitmex_balance_in_usd()
        binance_balance = self._get_binance_balance_in_usd()
        if bitmex_balance/binance_balance > 1+(self.warning_diff_percent/100):
            self.email_client.send_notification_about_balance(
                bitmex_balance=bitmex_balance,
                binance_balance=binance_balance)
        if calc_profit:
            self._calc_and_print_profit(bitmex_balance_btc, binance_balance)

        

    def _calc_and_print_profit(self, bitmex_balance_btc, binance_balance):
        pnl_bitmex = bitmex_balance_btc - self.bitmex_binance_balances_history[-1][1]
        pnl_binance = binance_balance - self.bitmex_binance_balances_history[-1][2]
        pnl_summary = round(pnl_bitmex*self._get_XBTUSD_price() + pnl_binance, 2)
        open('PnL(for debug).log', 'a').write('[{}]bx: {}, bn: {}, sum: {}\n'.format(
            datetime.now(), pnl_bitmex, pnl_binance, pnl_summary))
        self.bitmex_binance_balances_history.append(
            (int(time.time()), round(bitmex_balance_btc, 2), round(binance_balance, 2))
            )
        self._record_in_log('Результат сделки $: '+str(pnl_summary))
        self.PnL_history.append((int(time.time()), pnl_summary))
        return pnl_summary



    def _calc_initial_balances(self):
        self.balance_bitmex_start = self._get_bitmex_balance_in_btc()
        self.balance_binance_start = self._get_binance_balance_in_usd()
        self.bitmex_binance_balances_history.append(
            (int(time.time()), self.balance_bitmex_start, round(self.balance_binance_start, 3))
            )



    def _calc_amount_for_trade(self): # In USD
        amount = self._get_bitmex_balance_in_usd()*(self.amount_to_trade_percent/100)
        return int(amount)



    def _get_binance_position_amount(self):
        ETHUSDT_price = self.binance_ticker_receiver.bid_price
        for asset in self.binance_client.position_info():
            if asset['symbol']=='ETHUSDT':
                return {
                    'side_is_buy': True if asset['positionSide']=='BUY' else 'SELL',
                    'ETH': float(asset['positionAmt']),
                    'USD': float(asset['positionAmt'])*ETHUSDT_price,
                    }
        return {
            'ETH': 0,
            'USD': 0,
            }




    def _get_bitmex_position_amount(self):
        for n_error in range(5):
            try:
                for asset in self.bitmex_client.Position.Position_get().result()[0]:
                    if asset['symbol']=='ETHUSD':
                        return {'USD': int(asset['execQty']),}
                return {'USD': 0,}
            except Exception as er:
                print('Ошибка при получении позиции Bitmex, попытка через 5 сек:', str(er))
                time.sleep(5.5)



    def _get_bitmex_balance_in_usd(self):
        balance_usd = self._get_bitmex_balance_in_btc()*self._get_XBTUSD_price()
        return round(balance_usd, 3)



    def _get_bitmex_balance_in_btc(self):
        for n_errors in range(1, 6):
            try:
                wallet_info = self.bitmex_client.User.User_getMargin().result()[0]
                balance = wallet_info['walletBalance']+wallet_info['unrealisedPnl']
                return balance/(10**8)
            except Exception as er:
                print('Ошибка при получени баланса bitmex:', str(er))
                time.sleep(5.5)



    def _get_binance_balance_in_usd(self):
        return float(self.binance_client.balance()[0]['balance'])



    def _get_XBTUSD_price(self): #from bitmex
        for n_errors in range(1,6):
            try:
                price = requests.get('https://www.bitmex.com/api/v1/orderBook/L2?symbol=XBTUSD&depth=1').json()[0]['price']
                return float(price)
            except Exception as e:
                print('XBTUSD price get error:', str(e))
                time.sleep(5.5)



    @in_new_thread
    def _print_balances(self):
        bitmex_btc = self._get_bitmex_balance_in_btc()
        bitmex_usd = round(bitmex_btc*self._get_XBTUSD_price(), 2)
        binance_usd = round(self._get_binance_balance_in_usd(), 2)
        self._record_in_log('Балансы: Binance: {}$, Bitmex: {} BTC({}$)'.format(
            binance_usd, bitmex_btc, bitmex_usd))



    @in_new_thread
    def _record_spread(self, spread):
        if self.spread_recorder_is_need_to_close:
            self.spread_recorder_is_need_to_close = False
            self.spreads_tmp.append(spread)
            self.spread_records.append((int(time.time()), spread))
            if abs(min(self.spread_tmp)) > abs(max(self.spread_tmp)):
                spread = min(self.spread_tmp)
            else:
                spread = max(self.spread_tmp)
            self.spread_records.append((int(time.time()), spread))
            self.spreads_tmp = []
            time.sleep(10)
            self.spread_recorder_is_need_to_close = True
        else:
            self.spreads_tmp.append(spread)



    def _record_in_log(self, text, color='black'):
        dt = datetime.now().astimezone(tz.gettz(TIMEZONE_FOR_LOG))
        text_to_print = '\n[{}:{}:{}] {}'.format(dt.hour, dt.minute, dt.second, text)
        print(text_to_print)
        open('log.log', 'a').write(text_to_print)
        self.web_log_records.append(LogRecord(dt=dt, text=text, color=color))



    def clear_web_log(self):
        self.web_log_records = []



    def stop(self):
        self.ON = False
