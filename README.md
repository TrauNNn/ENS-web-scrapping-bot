# ENS-web-scrapping-bot
Telegram bot which will parse .eth domains and show available domains for you. 
Recommended limit of stored domains is 5000, but if you want you can store more.

### Used technologies:
- Python 3.10.0
- MS Access 2016 (download driver for odbc from https://www.microsoft.com/en-us/download/details.aspx?id=54920)
- JSON

### Python packages:
- Selenium
- BeautifulSoup4
- telebot
- webdriver_manager

### How to use:
- write "/start" to your bot
- use the keyboard for calling methods, which can show you some information about stored domains, or will ask you to insert/delete domains
- for input methods use text files with domains written in column, or write them as message like that: "domain notdomain anotherdomain"
