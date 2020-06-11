from bitmex import bitmex

from resources.binance_futures import binance_futures
from resources.strategy_logic import Strategy
from resources.email_client import EmailClient
from resources.utils import in_new_thread
from resources.binance_ticker_receiver import BinanceTickerReceiver
from resources.bitmex_ticker_receiver import BitmexTickerReciever

from web_manager import web

binance_ticker_receiver = BinanceTickerReceiver()
bitmex_ticker_receiver = BitmexTickerReciever()

STRATEGY = [None,]

@in_new_thread
def FUNC_FOR_START(
    api_key_binance, api_secret_binance,
    api_key_bitmex, api_secret_bitmex,
    percent_to_trade, bottom_spread, top_spread, email):
    global binance_ticker_receiver, bitmex_ticker_receiver
    binance_client = binance_futures.Client(
        api_key_binance,
        api_secret_binance,
        symbol='ETHUSDT',
        testnet=False,)

    bitmex_client = bitmex(
        test=False,
        api_key=api_key_bitmex,
        api_secret=api_secret_bitmex,)

    email_client = EmailClient(login='arbitrage.bot@inbox.ru',
        password='AtDrsinYK42_',
        smtp_server='smtp.mail.ru',
        target_email=email,)

    STRATEGY[0] = Strategy(binance_client=binance_client,
        binance_ticker_receiver=binance_ticker_receiver,
        bitmex_client=bitmex_client,
        bitmex_ticker_receiver=bitmex_ticker_receiver,
        email_client=email_client,
        amount_to_trade_percent=float(percent_to_trade),
        bottom_spread=float(bottom_spread),
        top_spread=float(top_spread),
        warning_diff_percent=10,) #  Для отправки разницы на почту)
    STRATEGY[0].start()


@in_new_thread
def FUNC_FOR_STOP():
    global STRATEGY
    STRATEGY[0].stop()

if __name__=='__main__':
    web.FUNC_FOR_START = FUNC_FOR_START
    web.FUNC_FOR_STOP = FUNC_FOR_STOP
    web.STRATEGY = STRATEGY
    web.app.run('0.0.0.0', '5050')
