  
<h1 align="center">Pinterest Telegram Bot</h1>

<p align="center">
<a href="https://github.com/Dineshkarthik/pinterest-telegram-bot/blob/master/LICENSE"><img alt="License: MIT" src="https://black.readthedocs.io/en/stable/_static/license.svg"></a>
<a href="https://github.com/python/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

### Overview:
A Telegram bot that downloads videos, images, GIFs from Pinterest based on user input and sends it back to the user via Telegram.

![demo](demo.gif)


### Support:
| Category | Support |
|--|--|
|Language | `Python 3.6 ` and above|



### Installation

```sh
$ git clone https://github.com/Dineshkarthik/pinterest-telegram-bot.git
$ cd pinterest-telegram-bot
$ pip3 install -r requirements.txt
```


## Configuration 

    TOKEN: 'YOUR_BOT_TOKEN'
    WEBHOOK_URL: 'https://<YOUR_APP_NAME>.herokuapp.com'
    REDIS_URL: 'redis://<USER_NAME>:<PASSWORD>@<HOST>:<PORT>'


 - token  - Your Telegram Bot API Token, to get the token follow the instructions available [here](https://core.telegram.org/bots#6-botfather).
 - webhook_url - Heroku app url. Instructions for deploying a python to heroku app can be found [here](https://devcenter.heroku.com/articles/getting-started-with-python).
 - redis_url - Redis is used to cache scraped urls to increase performance, check how to use heroku redis [here](https://devcenter.heroku.com/articles/heroku-redis).


## Execution
```sh
$ python3 pinterest_telegram_bot.py
```
