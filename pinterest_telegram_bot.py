import os
import json
import logging
import re
from typing import Optional, Tuple

import redis
import requests
import tldextract
from bs4 import BeautifulSoup
from flask import Flask, request
from telebot import TeleBot, types, apihelper

logging.basicConfig(level=logging.INFO)

server = Flask(__name__)
THIS_DIR: str = os.path.dirname(os.path.abspath(__file__))
server.config.from_pyfile(os.path.join(THIS_DIR, "config.py"))

TOKEN: str = server.config["TOKEN"]
bot = TeleBot(TOKEN)
rdb = redis.from_url(server.config["REDIS_URL"])


class InvalidUrlError(Exception):
    """Not a valid url exception"""

    pass


class InvalidPinterestUrlError(Exception):
    """Not a Pinterest url exception"""

    pass


def extract_url(text: str) -> Optional[str]:
    """Extracts url from text

    Parameters
    ----------
    text : str
        String from which url to be extracted.

    Returns
    -------
    Optional[str]
        Return url if present in the given string.
    """
    regex_extract = re.search("(?P<url>https?://[^\s]+)", text)
    return regex_extract.group("url") if regex_extract else None


def read_url(_url: str) -> BeautifulSoup:
    """Crawls the given URL.

    Parameters
    ----------
    _url : str
        URL to crawl.

    Returns
    -------
    BeautifulSoup
        Returns crawled webpage as a BeautifulSoup object.

    Raises
    ------
    InvalidPinterestUrlError
        If the given url is not a pinterest url.
    InvalidUrlError
        If the given url is not a valid/active url.
    """
    try:
        r = requests.get(
            _url, headers=server.config["HEADERS"], allow_redirects=True
        )
        if tldextract.extract(r.url).domain != "pinterest":
            raise InvalidPinterestUrlError(
                f"'{_url}' not a valid Pinterest url"
            )
        resp = requests.get(
            r.url.split("/sent")[0],
            headers=server.config["HEADERS"],
            allow_redirects=True,
        )
    except Exception as e:
        raise InvalidUrlError(f"'{_url}' not a valid url")
    return BeautifulSoup(resp.text, features="html.parser")


def extract_video(json_load: dict) -> Tuple[Optional[str], int]:
    """Extracts video url from dict

    Parameters
    ----------
    json_load : dict
        Json load from crawled webpage.

    Returns
    -------
    Tuple[Optional[str], int]
        Video url, video duration
    """
    try:
        video_resp: str = (
            json_load.get("resourceResponses", [{}])[0]
            .get("response", {})
            .get("data", {})
            .get("videos", {})
            .get("video_list", {})
            .get("V_720P", {})
        )
        video_url: str = video_resp.get("url", None)
        duration: int = video_resp.get("duration", 0)
    except Exception as excp:
        video_url = None
        duration = 0
    return video_url, duration


def extract_image(json_load: dict) -> Optional[str]:
    """Extracts image url from dictionary.

    Parameters
    ----------
    json_load : dict
        Json load from crawled webpage.

    Returns
    -------
    Optional[str]
        Image url if present.
    """
    try:
        img_url: str = (
            json_load.get("resourceResponses", [{}])[0]
            .get("response", {})
            .get("data", {})
            .get("images", {})
            .get("orig", {})
            .get("url", None)
        )
    except Exception as excp:
        img_url = None
    return img_url


@bot.message_handler(commands=["download", "Download"])
def download_image(message: types.Message):
    """`/download` command handler.

    Parameters
    ----------
    message : types.Message
        Message object from telegram.
    """
    text = (
        "Hi,\nI am an updated bot now, "
        "you don't need to use the `/download` just send the URL"
    )
    bot.send_chat_action(message.chat.id, "typing")
    msg = bot.send_message(message.chat.id, text, parse_mode="MARKDOWN")


def send_image(message: types.Message, url: str):
    """Sends reply back to the user.

    Parameters
    ----------
    message : types.Message
        Message object from telegram.

    url : str
        url to be crawled.
    """
    try:
        cached_url = rdb.get(url)
        if not cached_url:
            soup_data = read_url(url)
            json_load = json.loads(
                str(soup_data.find("script", {"id": "initial-state"})).strip(
                    """<script id="initial-state" type="application/json">"""
                )
            )
            image_url = (
                extract_image(json_load)
                or soup_data.find("meta", {"name": "og:image"})["content"]
            )
            video_url, video_duration = extract_video(json_load)
            rdb.set(url, json.dumps({"image": image_url, "video": video_url}))
            rdb.expire(url, 1200)
        else:
            cached_url = json.loads(cached_url)
            image_url = cached_url.get("image")
            video_url = cached_url.get("video")
            logging.info(
                "Cache: used for %s requested by chat id - %s",
                url,
                message.chat.id,
            )
        if not video_url:
            bot.send_chat_action(message.chat.id, "upload_photo")
            if image_url.endswith(".gif"):
                media_type: str = "Gif"
                bot.send_document(message.chat.id, image_url)
            else:
                media_type = "Image"
                bot.send_photo(message.chat.id, image_url)
        else:
            bot.send_chat_action(message.chat.id, "upload_video")
            media_type = "Video"
            try:
                bot.send_video(message.chat.id, video_url)
            except apihelper.ApiException as e:
                media_type = "Video too large"
                bot.send_message(
                    message.chat.id,
                    (
                        "Unable to send video here in chat this may be due to "
                        "Telegram Bots API send file [size limitation](https://core.telegram.org/bots/api#sending-files)\n"
                        "the video is too large for the bot to share here.\n"
                        f"*Please download video from* [here]({video_url})"
                    ),
                    parse_mode="MARKDOWN",
                    disable_web_page_preview=True,
                )
        bot.send_message(
            message.chat.id,
            "[🥤 Buy Me a Coffee](https://www.buymeacoffee.com/deekay)",
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )
        logging.info(
            "%s from url %s sent to chat id - %s",
            media_type,
            url,
            message.chat.id,
        )
    except InvalidUrlError:
        bot.send_message(
            message.chat.id,
            f"Invalid url - {url}.\nPlease check the url and retry.",
            disable_web_page_preview=True,
        )
    except InvalidPinterestUrlError:
        bot.send_message(
            message.chat.id,
            (
                f"Not a Pinterest url - {url}.\n"
                "Please try with a Pinterest image or video URL."
            ),
            disable_web_page_preview=True,
        )
    except Exception as e:
        error_message = (
            f"Internal Error occured when downloading - {url}.\n"
            "For support contact - [Pinterest Downloader Support Channel](https://t.me/joinchat/TPZF7pxnsnI25Olv)"
        )
        logging.error("Unable to download url - %s due to error %s", url, e)
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )


@bot.message_handler(commands=["start", "help"])
def send_instructions(message: types.Message):
    """`/start` and `/help` command handler.

    Parameters
    ----------
    message : types.Message
        Message object from telegram.
    """
    bot.send_chat_action(message.chat.id, "typing")
    msg_content: str = (
        f"Hi {message.from_user.first_name}\n"
        "To know how to download see this video - https://youtu.be/gffp9_U5lLs"
    )
    bot.send_message(
        message.chat.id,
        msg_content,
    )


@bot.message_handler(func=lambda m: True)
def default_message(message: types.Message):
    """Default message handler.

    Parameters
    ----------
    message : types.Message
        Message object from telegram.
    """
    logging.info(
        "%s - requested to download %s", message.chat.id, message.text
    )
    url: str = extract_url(message.text)
    if url:
        send_image(message, url)
    else:
        bot.send_chat_action(message.chat.id, "typing")
        msg_content: str = (
            f"Hi {message.from_user.first_name},\n\n"
            f"Invalid url - {message.text}.\nPlease check the url and retry."
        )
        bot.send_message(
            message.chat.id,
            msg_content,
            disable_web_page_preview=True,
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
