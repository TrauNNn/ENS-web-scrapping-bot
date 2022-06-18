from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import pyodbc
import telebot
from telebot import types

import traceback
import random
import time
import threading
import json
import datetime
from datetime import date


def conn_telegram_api(key): #'2099275622:AAHPA1vuU84HiK9xQf9RkvGLSAAHrbJ1HLM'
    keyboards = {}
    data = json.load(open("keyboards.json", "r"))
    for keyboard_name in data:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for key_name in data:
            key = types.KeyboardButton(text=data[key_name])
            keyboard.add(key)
        keyboards[keyboard_name] = {keyboard_name: keyboard}
    return telebot.TeleBot(key, threaded=True), keyboards


def double_split(text, key1, key2):
    text = str(text)
    return text.split(key1)[1].split(key2)[0]


def time_comparing_minutes(time_for_comparison):
    time_hours, time_minutes = time_for_comparison.split(':')
    now = datetime.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_from_midnight = int(time_hours)*60 + int(time_minutes)
    minutes_now = round((now - midnight).seconds / 60)
    return minutes_from_midnight - minutes_now


def conn_to_local_database():
    return pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        r"DBQ=C:\Users\Administrator\Desktop\ethereum-domains-bot\updated\domains.accdb;"
    ).cursor()


def execute_query(db_cursor, query_name: str, query_args: tuple, output: bool):
    if output:
        db_cursor.execute("DROP TABLE output")
    db_cursor.execute("{CALL " + query_name + " " + str(query_args) + "}")
    db_cursor.commit()
    if output:
        db_cursor.execute("SELECT * FROM output")
        return db_cursor.fetchall()
    return True


def get_selenium_browser():
    options = Options()
    options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    browser = webdriver.Chrome(ChromeDriverManager().install())
    browser.get('https://app.ens.domains/')
    time.sleep(3)
    return browser


def search_for_domain(domain_name, browser, db_cursor):
    browser.get('https://app.ens.domains/')
    time.sleep(3)

    html_of_profile = browser.page_source
    soup = BeautifulSoup(str(html_of_profile), 'lxml')

    quotes = browser.find_elements_by_xpath("//input[@placeholder='Search names or addresses']")

    if len(quotes) == 0:
        time.sleep(4)
        return "the page is not ready, correct time.sleep amounts or check your internet connection"

    quotes[0].click()
    quotes[0].send_keys(domain_name + Keys.ENTER)
    time.sleep(3)
    status = get_domain(browser.page_source, db_cursor, domain_name)
    return status


def get_domain(html_of_profile, db_cursor, domain_name):
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
            outdated_day = outdated_day.split('.')[1] + '/' + outdated_day.split('.')[2] + '/' + outdated_day.split('.')[0]
            outdated_time = double_split(quotes[0].text, 'at ', '(UTC').replace(' ', '')
            if len(outdated_time.split(':')[0]) < 2:
                outdated_time = '0' + outdated_time
            if len(outdated_time.split(':')[1]) < 2:
                outdated_time = outdated_time.split(':')[0] + ':' + '0' + outdated_time.split(':')[1]

        if outdated_time is not None:
            query_args = (outdated_day, outdated_time, False, False, domain_name, False)
            execute_query(db_cursor, "update_domains_data", query_args, False)
        else:
            return "expiry time or date is not found"
        return 'Unavailable'

    if quotes[0].text == 'Available':
        premium_required = True if "Available with a temporary premium" in str(soup) else False
        query_args = ("Date()",
                      f"'{datetime.datetime.now().hour}:{datetime.datetime.now().minute}'",
                      True,
                      True,
                      premium_required,
                      domain_name)
        execute_query(db_cursor, "update_domains_data", query_args, False)
        return "premium required" if premium_required else "Available"


def get_notifications(db_cursor, browser):
    domains = []
    raw_data = execute_query(db_cursor, "find_domains_with_notification", (), True)
    for domain_id in range(0, len(raw_data)):
        if time_comparing_minutes(raw_data[domain_id][1]) < 12:
            search_for_domain(raw_data[domain_id][0], browser, db_cursor)
            updated_time = execute_query(db_cursor, "time_by_domain_name", (raw_data[domain_id][0]), True)[0]
            if time_comparing_minutes(updated_time[0]) < 12:
                domains.append((raw_data[domain_id][0], raw_data[domain_id][2]))
                execute_query(db_cursor, "set_domain_as_not_checked", (raw_data[domain_id][0]), False)

    return domains


def get_domains_close_to_time(db_cursor):
    raw_data = execute_query(db_cursor, "get_domains_close_to_expiry", (), True)
    for domain_name in range(0, len(raw_data) ):
        raw_data[domain_name] = raw_data[domain_name][0]
        
    return raw_data


def update_domains_status(db_cursor):
    db_cursor.execute(f"UPDATE domains SET IsChecked = False, OutdatedDay = Date() WHERE OutdatedDay < Date()")
    db_cursor.commit()
    db_cursor.execute(f"SELECT domainName FROM domains WHERE (IsChecked = False AND OutdatedDay = Date() )")


def add_domains_to_database(list_of_domains, db_cursor):
    to_return = []
    for to_push in list_of_domains:
        to_push = to_push.replace(' ', '').replace('\n', '')
        db_cursor.execute(f"SELECT domainName FROM domains WHERE ( domainName = '{to_push}')")
        if len(db_cursor.fetchall() ) == 0 and len(to_push) > 2:
            db_cursor.execute(f"INSERT INTO domains VALUES ('{to_push}', False, Date(), '0:00', False, False, False)")
        db_cursor.commit()
    return to_return


def remove_domains_from_database(list_of_domains, db_cursor):
    for to_remove in list_of_domains:
        to_remove = to_remove.replace(' ', '').replace('\n', '')
        db_cursor.execute(f"SELECT domainName FROM domains WHERE ( domainName = '{to_remove}')")
        if len(db_cursor.fetchall() ) == 1:
            db_cursor.execute(f"DELETE FROM domains WHERE ( domainName = '{to_remove}')")
    db_cursor.commit()


bot, keyboards = conn_telegram_api("2099275622:AAHPA1vuU84HiK9xQf9RkvGLSAAHrbJ1HLM")


@bot.message_handler(content_types=['text'])
def message_get(message, db_cursor, keyboard):
    db_cursor.execute(f"SELECT eventtype, answer, header_file, key FROM telebot_events WHERE key = '{message.text}'")
    telebot_event = db_cursor.fetchone()

    if telebot_event == None:
        db_cursor.execute(f"SELECT nextaction, hasaccess FROM users WHERE tgID = {message.from_user.id}")
        user_info = db_cursor.fetchone()
        if not (user_info[1]):
            bot.send_message(message.from_user.id,
                             'Access denied')
            return None

        if user_info[0] == 'Select domains with notification':
            domains = message.text.split(' ')
            for domain in domains:
                try:
                    db_cursor.execute(
                        f"INSERT INTO domains VALUES ('{domain}', False, Date(), '00:00', False, {message.from_user.id}, True)")
                except:
                    db_cursor.execute(f"UPDATE domains SET IsSelected = True WHERE domainName = '{domain}'")
        if user_info[0] == 'Remove notification from domains':
            domains = message.text.split(' ')
            for domain in domains:
                try:
                    db_cursor.execute(
                        f"INSERT INTO domains VALUES ('{domain}', False, Date(), '00:00', False, {message.from_user.id}, False)")
                except:
                    db_cursor.execute(f"UPDATE domains SET IsSelected = False WHERE domainName = '{domain}'")
        db_cursor.commit()
        return None

    text_to_send = telebot_event[1] + '\n'
    send_with_file = False

    if telebot_event[0] == 'get':
        file_to_send = open(f'{telebot_event[1]}.csv', 'w')
        db_cursor.execute(f"SELECT result FROM {message.text.replace(' ', '_')}")
        raw_data = db_cursor.fetchall()
        file_to_send.write(telebot_event[2] + '\n')

        for cell in raw_data:
            try:
                print(str(cell))
                if len(str(cell).split(',')[2].split(':')[0]) < 2:
                    cell_arr = str(cell)[0].split(',')
                    cell = cell_arr[0] + ',' + cell_arr[1] + ',0' + cell_arr[2].split(':')[0] + ':' + \
                           cell_arr[2].split(':')[1] + ',' + cell_arr[3] + ',' + cell_arr[4]
                if len(str(cell).split(',')[2].split(':')[1]) < 2:
                    cell_arr = str(cell)[0].split(',')
                    cell = cell_arr[0] + ',' + cell_arr[1] + ',' + cell_arr[2].split(':')[0] + ':0' + \
                           cell_arr[2].split(':')[1] + ',' + cell_arr[3] + ',' + cell_arr[4]
            except:
                pass
            file_to_send.write(cell[0].replace('\n', '').replace(',-1..', ',Yes').replace(',0..', ',No') + '\n')
        file_to_send.close()
        send_with_file = True

    if telebot_event[0] == 'execute':
        try:
            db_cursor.execute(f"INSERT INTO users VALUES ({message.from_user.id}, False, '{telebot_event[3]}')")
        except:
            db_cursor.execute(
                f"UPDATE users SET nextaction='{telebot_event[3]}' WHERE tgID = {message.from_user.id}")
        db_cursor.commit()

    if send_with_file:
        bot.send_document(message.from_user.id,
                          open(f'{telebot_event[1]}.csv'),
                          reply_markup=keyboard)

    else:
        bot.send_message(message.from_user.id,
                         text_to_send,
                         reply_markup=keyboard)


if __name__ == "__main__":
    get_selenium_browser()
    conn_to_local_database()
    #search_for_domain(domain_name, browser, db_cursor)

