import time
import hashlib

from flask import Flask, render_template
from flask import request



app = Flask(__name__)


FUNC_FOR_START = None
FUNC_FOR_STOP = None
STRATEGY = None


IS_BOT_RUNNING = False
DEFAULT_BOTTOM_SPREAD = -0.1
DEFAULT_TOP_SPREAD = 0.6
DEFAULT_BALANCE_PERCENT = 100
DEFAULT_WARNING_EMAIL = 'test123@gmail.ru'
DEFAULT_WARNING_DIFF_PERCENT_BALANCE = 10


def get_valid_hashed_password():
    '''Получает правильный хэшированный пароль из txt файла'''
    return '6ae190de04d9c421f83400ab92e72bf38fc6ca2f' # затычка
    with open('web_manager/hashed_password_for_web.txt', 'r') as f:
        pwd = f.read().strip()
    return pwd



########### Views:
@app.route('/')
def main_page():
    return render_template('index.html', is_bot_started=IS_BOT_RUNNING)


@app.route('/start_bot', methods=['GET', 'POST'])
def start_bot():
    global IS_BOT_RUNNING
    if IS_BOT_RUNNING:
        return 'Бот уже запущен'

    if request.method=='POST':
        api_key_bitmex = request.form.get('api_key_bitmex')
        api_secret_bitmex = request.form.get('api_secret_bitmex')
        api_key_binance = request.form.get('api_key_binance')
        api_secret_binance = request.form.get('api_secret_binance')
        percent_to_trade = request.form.get('percent_to_trade')
        bottom_spread = request.form.get('bottom_spread')
        top_spread = request.form.get('top_spread')
        email = request.form.get('email')
        hashed_received_pwd = hashlib.sha1(request.form.get('password').encode('utf-8')).hexdigest()
        if not hashed_received_pwd==get_valid_hashed_password():
            time.sleep(4)
            return 'Введен неправильный пароль'
        FUNC_FOR_START(
            api_key_binance=api_key_binance,
            api_secret_binance=api_secret_binance,
            api_key_bitmex=api_key_bitmex, 
            api_secret_bitmex=api_secret_bitmex, 
            percent_to_trade=percent_to_trade, 
            bottom_spread=bottom_spread, 
            top_spread=top_spread, 
            email=email)
        IS_BOT_RUNNING = True
        return 'Бот запущен'

    if request.method=='GET':
        return render_template('start_bot.html', is_bot_started=IS_BOT_RUNNING)


@app.route('/stop_bot', methods=['GET', 'POST'])
def stop_bot():
    if request.method=='POST':
        hashed_received_pwd = hashlib.sha1(request.form.get('password').encode('utf-8')).hexdigest()
        if not hashed_received_pwd==get_valid_hashed_password():
            time.sleep(4)
            return 'Введен неправильный пароль'
        else:
            IS_BOT_RUNNING = False
            FUNC_FOR_STOP()
    if request.method=='GET':
        return render_template('stop_bot.html')



@app.route('/log')
def log():
    render_template('log.html', log_records=STRATEGY.web_log_records)



'''
if __name__=='__main__':
    app.run('localhost', '80')
'''