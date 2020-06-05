# -*- coding: utf-8 -*-
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from threading import Thread


class EmailClient:
    def __init__(self,
        login='arbitrage.bot@inbox.ru',
        password='AtDrsinYK42_',
        smtp_server='smtp.mail.ru',
        target_email='vladkanal@gmail.com',):
        self.login = login
        self.password = password
        self.smtp_server = smtp_server + ':587'
        self.target_email = target_email


    def send_notification_about_balance(self, bitmex_balance, binance_balance):
        def send():
            mail_client = smtplib.SMTP(self.smtp_server)

            subject = u'Оповещение о состоянии баланса от арбитражного бота'
            body = u'Баланс на\n\nBitmex: {}$.\nBinance: {}$.'.format(round(bitmex_balance), round(binance_balance))
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = Header(subject, 'utf-8')
            # Отпавляем письмо
            mail_client.starttls()
            mail_client.ehlo()
            mail_client.login(self.login, self.password)
            mail_client.sendmail(self.login, self.target_email, msg.as_string())
            mail_client.quit()
        Thread(target=send).start()
