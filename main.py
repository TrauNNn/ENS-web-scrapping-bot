from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import pyodbc
import telebot
from telebot import types

import os
import time
import threading
import json
import datetime


def get_telegram_keyboards():
    keyboards = {}
    data = json.load(open("keyboards.json", "r"))
    for keyboard_name in data:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for key_name in data[keyboard_name]:
            key = types.KeyboardButton(text=key_name)
            keyboard.add(key)
        keyboards[keyboard_name] = keyboard
    return keyboards


def double_split(text, key1, key2):
    text = str(text)
    return text.split(key1)[1].split(key2)[0]


def conn_to_local_database():
    db_cursor = pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"DBQ={os.path.dirname(os.path.realpath(__file__))}/domains.accdb;"
    ).cursor()
    print("connected")
    return db_cursor


def execute_query(db_cursor, query_name: str, query_args: tuple, output: bool):
    query_name = query_name.replace("'", "")
    if output:
        db_cursor.execute("DROP TABLE output")
    db_cursor.execute("{CALL " + query_name + " " + str(query_args) + "}")
    db_cursor.commit()
    if output:
        db_cursor.execute("SELECT * FROM output")
        to_return = db_cursor.fetchall()
        return to_return if len(to_return) != 1 else to_return[0]
    return True


def get_selenium_browser():
    options = Options()
    options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    browser = webdriver.Chrome(ChromeDriverManager().install())
    browser.get('https://app.ens.domains/')
    time.sleep(4)
    return browser


def search_for_domain(domain_name, browser, db_cursor):
    browser.get('https://app.ens.domains/')
    time.sleep(4)

    html_of_profile = browser.page_source
    soup = BeautifulSoup(str(html_of_profile), 'lxml')

    quotes = browser.find_elements_by_xpath("//input[@placeholder='Search names or addresses']")

    if len(quotes) == 0:
        time.sleep(3)
        return "the page is not ready, correct time.sleep amounts or check your internet connection"

    quotes[0].click()
    quotes[0].send_keys(domain_name)
    time.sleep(2)
    quotes[0].send_keys(Keys.ENTER)
    time.sleep(7)
    try:
        get_domain_into_database(browser.page_source, db_cursor, domain_name)
    except:
        return "the page is not ready, correct time.sleep amounts or check your internet connection"


def get_domain_into_database(html_of_profile, db_cursor, domain_name):
    soup = BeautifulSoup(str(html_of_profile), 'lxml')
    quotes = soup.find_all('div', class_='css-0')  # css-0 e1736otp6

    if quotes[0].text == 'Unavailable':
        outdated_day = None
        outdated_time = None
        quotes = soup.find_all('p', class_='css-1cuem9r')  # css-1cuem9r erk1q1g0
        if len(quotes) > 0:
            outdated_day = double_split(quotes[0].text, 'Expires ', ' at').replace(' ', '')
        else:
            quotes = soup.find_all('p', class_='css-htsl25')  # css-htsl25 erk1q1g0
            if 'ends ' in quotes[0].text:
                outdated_day = double_split(quotes[0].text, 'ends ', ' at').replace(' ', '')
            if 'Expires ' in quotes[0].text:
                outdated_day = double_split(quotes[0].text, 'Expires ', ' at').replace(' ', '')

        if outdated_day is not None:
            outdated_day = outdated_day.split('.')[1] + '/' + outdated_day.split('.')[2] + '/' + \
                           outdated_day.split('.')[0]
            outdated_time = double_split(quotes[0].text, 'at ', '(UTC').replace(' ', '')

        if outdated_time is not None:
            query_args = (outdated_day, outdated_time, 0, 0, domain_name)
            execute_query(db_cursor, "update_domain_data", query_args, False)
        else:
            pass

    if quotes[0].text == 'Available':
        query_args = (str(datetime.date.today()), f"00:00", -1, -1, domain_name)
        execute_query(db_cursor, "update_domain_data", query_args, False)


key = ''  # get it from config
bot = telebot.TeleBot(key, threaded=False)
database_cursor = conn_to_local_database()
mode = None


@bot.message_handler(content_types=['text'])
def message_get(message):
    db_cursor = conn_to_local_database()
    try:
        telebot_event = execute_query(db_cursor, "get_event", ("'" + message.text + "'"), True)

        global mode
        if not len(telebot_event):
            if mode is not None:
                query_args = message.text.split(' ')
                text_to_send = 'query succeed with:\n'

                for arg in query_args:
                    if execute_query(db_cursor, mode, ("'" + arg + "'"), False):
                        text_to_send += arg + ', '
                bot.send_message(message.from_user.id,
                                 text_to_send,
                                 reply_markup=keyboards["menu"])
                return True

            else:
                bot.send_message(message.from_user.id,
                                 "wrong command, or you have not chosen action",
                                 reply_markup=keyboards["menu"])
                return False

        text_to_send = telebot_event[1] + '\n'
        mode = None if telebot_event[0] != 'execute' else telebot_event[4].replace(" ", "_")

        if telebot_event[0] == 'get':
            file_to_send = open(f'{telebot_event[1]}.csv', 'w')
            raw_data = execute_query(db_cursor, message.text.replace(' ', '_'), (), True)
            file_to_send.write(telebot_event[2] + '\n')

            for cell in raw_data:
                file_to_send.write(str(cell[0]).replace('\n', '').replace(',-1..', ',Yes').replace(',0..', ',No') + '\n')
                """
                cell has type list with never more than 1 element, 
                where the string object contains at 0 place.
                -1 and 0 are True and False in MS Access, 
                two dots are written in queries to make python recognize -1 and 0 as their bool values.
                """
            file_to_send.close()
            bot.send_document(message.from_user.id,
                              open(f'{telebot_event[1]}.csv'),
                              reply_markup=keyboards["menu"])
            return True

        bot.send_message(message.from_user.id, text_to_send, reply_markup=keyboards["menu"])
        time.sleep(1)
        return True

    except:
        bot.send_message(message.from_user.id, "Something went wrong, check your message is it correct",
                         reply_markup=keyboards["menu"])
        return False


def worker(browser, db_cursor):
    execute_query(db_cursor, "set_domains_unchecked", (), False)
    to_parse = execute_query(db_cursor, "get_domains_close_to_expiry", (), True)
    for domain_name in range(0, len(to_parse)):
        search_for_domain(to_parse[domain_name][0], browser, db_cursor)


if __name__ == "__main__":
    keyboards = get_telegram_keyboards()
    web_browser = get_selenium_browser()

    backend = threading.Thread(target=worker, args=(web_browser, conn_to_local_database()))
    telegram_bot = threading.Thread(target=bot.infinity_polling)

    telegram_bot.start()
    backend.start()

    telegram_bot.join()
    backend.join()
