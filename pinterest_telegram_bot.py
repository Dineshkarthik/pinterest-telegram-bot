import os
import logging

import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from telebot import TeleBot, types

logging.basicConfig(level=logging.INFO)

server = Flask(__name__)
THIS_DIR: str = os.path.dirname(os.path.abspath(__file__))
server.config.from_pyfile(os.path.join(THIS_DIR, "config.py"))

TOKEN: str = server.config["TOKEN"]
bot = TeleBot(TOKEN)


class InvalidUrlError(Exception):
    """Base class for other exceptions"""

    pass


def get_image(_url: str):
    r = requests.get(
        _url, headers=server.config["HEADERS"], allow_redirects=True
    )
    soup = BeautifulSoup(r.text, features="html.parser")
    img_url: str = soup.find("meta", {"name": "og:image"})["content"]
    img = requests.get(img_url)
    return img.content


@bot.message_handler(commands=["download", "Download"])
def download_image(message):
    """/download."""
    text = "Please reply with the Pinterest URL to download image."
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, send_image)


def send_image(message):
    try:
        url: str = message.text
        logging.info("%s - requested to download %s", message.chat.id, url)
        if not url.startswith("http"):
            raise InvalidUrlError(f"'{url}' not a valid url")
        image_obj = get_image(url)
        bot.send_photo(message.chat.id, image_obj)
        bot.send_message(
            message.chat.id,
            "[🥤 Buy Me Coffee](https://www.buymeacoffee.com/deekay)",
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )
        logging.info(
            "Image from url %s sent to chat id - %s", url, message.chat.id
        )
    except InvalidUrlError:
        error_message = (
            f"Invalid url - {url}.\n"
            f"Please check the url and try after some time."
        )
        bot.send_message(
            message.chat.id, error_message,
        )
    except Exception as e:
        error_message = (
            f"Internal Error occured when downloading - {url}.\n"
            f"Please check the url and try after some time."
        )
        logging.error(e)
        bot.send_message(
            message.chat.id, error_message,
        )


@bot.message_handler(commands=["start", "help"])
def send_instructions(message):
    """/start, /help"""
    msg_content: str = (
        "*Available commands:*\n\n/download - downloads pinterest images"
    )
    bot.send_message(
        message.chat.id, msg_content, parse_mode="markdown",
    )


@bot.message_handler(func=lambda m: True)
def default_message(message):
    msg_content = """Hi, Please use /download command to download."""
    bot.send_message(
        message.chat.id, msg_content, parse_mode="markdown",
    )


@server.route("/" + TOKEN, methods=["POST"])
def getMessage():
    bot.process_new_updates(
        [types.Update.de_json(request.stream.read().decode("utf-8"))]
    )
    return "!", 200


@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=server.config["WEBHOOK_URL"] + TOKEN)
    return "!", 200


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
