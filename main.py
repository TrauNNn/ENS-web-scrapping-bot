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
    """
    returns dictionary with keyboard objects for bot.send_message methods
    """
    keyboards = {}
    data = json.load(open("keyboards.json", "r"))
    for keyboard_name in data:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for key_name in data[keyboard_name]:
            key = types.KeyboardButton(text=key_name)
            keyboard.add(key)
        keyboards[keyboard_name] = keyboard
    return keyboards


def double_split(text: str, key1: str, key2: str):
    """
    method is used for selection needed str fragment.
    '' as keys if you need to throw away only right (key1='') or left (key2='') part of text
    """
    text = str(text)
    return text.split(key1)[1].split(key2)[0]


def conn_to_local_database():
    """
    returns cursor
    database must be in the same directory with main.py
    """
    db_cursor = pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"DBQ={os.path.dirname(os.path.realpath(__file__))}/domains.accdb;"
    ).cursor()
    print('connected')
    return db_cursor


def execute_query(query_name: str, query_args: tuple, output: bool):
    """
    executes stored procedures
    if output is True returns the list of results
    will not work correctly if stored procedure returns 2 or more columns
    """
    try:
        db_cursor = conn_to_local_database()
        query_name = query_name.replace("'", "")
        db_cursor.execute("{CALL " + query_name + " " + str(query_args) + "}")
        db_cursor.commit()

        if output:
            db_cursor.execute(f"SELECT * FROM " + query_name + "_output")
            to_return = db_cursor.fetchall()
            db_cursor.execute(f"DROP TABLE {query_name}_output")
            db_cursor.commit()
            db_cursor.close()
            return to_return if len(to_return) != 1 else to_return[0]

        db_cursor.close()
        return True
    except:
        return () if output else False


def get_selenium_browser():
    """
    returns chrome browser with opened ENS website main page
    """
    options = Options()
    options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    browser = webdriver.Chrome(ChromeDriverManager().install())
    browser.get('https://app.ens.domains/')
    time.sleep(4)
    return browser


def search_for_domain(domain_name: str, browser):
    """
    returns html source of page with domain info
    change time.sleep args consider your internet connection
    """
    browser.get('https://app.ens.domains/')
    time.sleep(7)
    quotes = browser.find_elements_by_xpath("//input[@placeholder='Search names or addresses']")

    if len(quotes) == 0:
        time.sleep(4)
        return "the page is not ready, correct time.sleep amounts or check your internet connection"

    quotes[0].click()
    quotes[0].send_keys(domain_name)
    time.sleep(3)
    quotes[0].send_keys(Keys.ENTER)
    time.sleep(9)
    try:
        get_domain_info(browser.page_source, domain_name)
    except:
        return "the page is not ready, correct time.sleep amounts or check your internet connection"


def get_domain_info(html_of_profile, domain_name: str):
    """
    gets domain info from it's page html source code into database
    """
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
            execute_query("update_domain_data", query_args, False)
        else:
            pass

    if quotes[0].text == 'Available':
        query_args = (str(datetime.date.today()), f"00:00", -1, -1, domain_name)
        execute_query("update_domain_data", query_args, False)


key = ''  # in future get it from config
bot = telebot.TeleBot(key, threaded=False)
mode = None


@bot.message_handler(content_types=['text'])
def message_got(message):
    """
    bot method, returns False if not succeed with user's query
    firstly checks is message a command,
    if it's not, tries to complete last 'execute' query (mode) with given message as domains list
    """
    try:
        telebot_event = execute_query("get_event", ("'" + message.text + "'"), True)
        global mode
        if not len(telebot_event):
            if mode is not None:
                query_args = message.text.split(' ')
                text_to_send = 'query succeed with:\n'

                for arg in query_args:
                    arg = arg.replace(" ", ";;")
                    arg = arg.replace("\n", ";;")
                    arg = arg.replace("\r", "")
                    arg = arg.replace(",", ";;")
                    arg = arg.replace(";;;;", ";;")
                    if execute_query(mode, ("'" + arg + "'"), False):
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
            raw_data = execute_query(message.text.replace(' ', '_'), (), True)
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
        return True

    except:
        bot.send_message(message.from_user.id, "Something went wrong, check your message is it correct",
                         reply_markup=keyboards["menu"])
        return False


@bot.message_handler(content_types=['document'])
def file_got(message):
    """
    same with message_got, but only for completing 'execute' queries (mode)
    with domains list inside the file
    """
    global mode
    if mode is not None:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open('user_file', 'wb') as new_file:
            new_file.write(downloaded_file)

        text_to_send = 'query succeed with:\n'
        for args in open('user_file'):
            args = args.replace(" ", ";;")
            args = args.replace("\n", ";;")
            args = args.replace("\r", "")
            args = args.replace(",", ";;")
            args = args.replace(";;;;", ";;")
            args = args.split(';;')
            for arg in args:
                if execute_query(mode, ("'" + arg + "'"), False):
                    text_to_send += arg + ', '
        bot.send_message(message.from_user.id,
                         text_to_send,
                         reply_markup=keyboards["menu"])
        return True


def worker(browser):
    """
    infinity searching for unchecked domains, parsing them
    and after that starting notifying users
    notifications will not work until every domain is not checked
    """
    while True:
        execute_query("put_domains_in_queue", (), False)
        to_parse = execute_query("get_domains_close_to_expiry", (), True)
        for domain_name in range(0, len(to_parse)):
            search_for_domain(to_parse[domain_name][0], browser)
        notifications_worker()


def notifications_worker():
    """
    notifying about domains that become available soon
    every user which telegram account ID is stored in database
    """
    users = execute_query("get_all_users", (), True)
    notify_settings = json.load(open("notifications.json", "r"))
    for notification in notify_settings:
        to_send = execute_query("get_name_by_outdate_time", (notification,), True)
        for domain in to_send:
            for user in users:
                bot.send_message(user,
                                 f'Domain "{domain[0]}" '
                                 f'is going to become available in '
                                 f'{notify_settings[notification]}'
                                 f', if it is not re-bought',
                                 reply_markup=keyboards["menu"])
        time.sleep(60)


if __name__ == "__main__":
    """
    tried to put notification_worker into new thread,
    but caught lots of pyodbc errors
    """
    keyboards = get_telegram_keyboards()
    web_browser = get_selenium_browser()

    backend = threading.Thread(target=worker, args=(web_browser,))
    telegram_bot = threading.Thread(target=bot.infinity_polling)

    telegram_bot.start()
    backend.start()

    telegram_bot.join()
    backend.join()
