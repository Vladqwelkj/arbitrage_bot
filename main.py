from bitmex import bitmex

from resources.binance_futures import binance_futures
from resources.strategy_logic import Strategy
from resources.email_client import EmailClient
from resources.binance_ticker_receiver import BinanceTickerReceiver
from resources.bitmex_ticker_receiver import BitmexTickerReciever

binance_client = binance_futures.Client(
    'e5OelOe6n0vnAwrmH7W86Uee6phbMdKp66l85YlroAv9XhF45W3uI5aqCZRGYWVj',
    'hy5EACev7C5acknBDPfZ44WNA8OWPcNXYOhhOYjamVO5QZA5oPIPcZjqwUDP5RtU',
    symbol='ETHUSDT',
    testnet=False
    )

bitmex_client = bitmex(
    test=False,
    api_key='10OTgpO8u6tJYReF_9tpYXuT',
    api_secret='_I_1NPGhleO0EJwe2qfstyFz0NFleNgTwlNeuQV3Sa8t1lsv')

email_client = EmailClient(login='arbitrage.bot@inbox.ru',
    password='AtDrsinYK42_',
    smtp_server='smtp.mail.ru',
    target_email='vladkanal@gmail.com')
'''
print(bitmex_client.Position.Position_get().result())
exit()
bitmex_client.Order.Order_new( #Market
                   symbol = 'ETHUSD',
                   side = 'Buy',
                   orderQty = 1496,
                   ).result()'''

if __name__=='__main__':
    strategy = Strategy(binance_client=binance_client,
        binance_ticker_receiver=BinanceTickerReceiver(),
        bitmex_client=bitmex_client,
        bitmex_ticker_receiver=BitmexTickerReciever(),
        email_client=email_client,
        amount_to_trade_percent=5,

        warning_diff_percent=10,) #  Для отправки разницы на почту)
    strategy.start()