from cmath import log
import os
import json
import logging
import re
import random
import time
from typing import Optional, Tuple

import redis
import requests
import tldextract
from bs4 import BeautifulSoup
from flask import Flask, config, request
from telebot import TeleBot, types, apihelper

logging.basicConfig(level=logging.INFO)

server = Flask(__name__)
THIS_DIR: str = os.path.dirname(os.path.abspath(__file__))
server.config.from_pyfile(os.path.join(THIS_DIR, "config.py"))

TOKEN: str = server.config["TOKEN"]
bot = TeleBot(TOKEN)
rdb = redis.from_url(server.config["REDIS_URL"])

SUPPORT_MESSAGE: str = """
[💵 Donate via Stripe](https://donate.stripe.com/28o6s280ReHU3V6fYY)
[🥤 Buy Me a Coffee](https://www.buymeacoffee.com/deekay)
[💶 Donate via PayPal](https://paypal.me/dineshkarthikr)

[▶️ Subscribe to my Youtube Channel](https://www.youtube.com/channel/UC-qpRMgBCbjWSS0XfTWFcYQ)
"""


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


def call_pinterest_url_shortner_api(short_code: str) -> str:
    """Directly call the pinterest url shortner api to get full url.

    Parameters
    ----------
    short_code : str
        URL shortner code from shortned url.

    Returns
    -------
    Optional[str]
        Return full url ifretuened by the shortner api.

    """
    try:
        _url: str = f"https://api.pinterest.com/url_shortener/{short_code}/redirect/"
        r = requests.get(_url, headers=server.config["HEADERS"], allow_redirects=True)
        return r.url.split("/sent")[0]
    except Exception as e:
        logging.exception(e)


def scrap_url(_url: str) -> BeautifulSoup:
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
        r = requests.get(_url, headers=server.config["HEADERS"], allow_redirects=True)
        if tldextract.extract(r.url).domain != "pinterest":
            raise InvalidPinterestUrlError(f"'{_url}' not a valid Pinterest url")
        long_url = r.url.split("/sent")[0]
        if "/pin/" not in long_url:
            long_url = call_pinterest_url_shortner_api(_url.split("/pin.it/")[-1])
        resp = requests.get(
            long_url,
            headers=server.config["HEADERS"],
            allow_redirects=True,
        )
    except Exception as e:
        raise InvalidUrlError(f"'{_url}' not a valid url")
    soup_data = BeautifulSoup(resp.text, features="html.parser")
    json_load = json.loads(
        str(soup_data.find("script", {"id": "__PWS_DATA__"})).strip(
            """<script id="__PWS_DATA__" type="application/json">"""
        )
    )["props"]["initialReduxState"]
    og_image_url = soup_data.find("meta", {"name": "og:image"})["content"]
    return json_load, og_image_url


def extract_story(json_load: dict) -> Optional[str]:
    """Extracts video url from story block in dict

    Parameters
    ----------
    json_load : dict
        Json load from crawled webpage.

    Returns
    -------
    Optional[str]
        if present video url
    """
    try:
        pin_id: str = next(iter(json_load["pins"]))
        video_url: str = (
            json_load.get("pins", {})
            .get(pin_id, {})
            .get("story_pin_data", {})
            .get("pages", [[]])[0]
            .get("blocks", [{}])[0]
            .get("video", {})
            .get("video_list", {})
            .get("V_EXP7", {})
            .get("url", None)
        )
    except Exception as excp:
        video_url = None
    return video_url


def extract_video(json_load: dict) -> Optional[str]:
    """Extracts video url from dict

    Parameters
    ----------
    json_load : dict
        Json load from crawled webpage.

    Returns
    -------
    Optional[str]
        If present Video url
    """
    try:
        pin_id: str = next(iter(json_load["pins"]))
        video_url: str = (
            json_load.get("pins", {})
            .get(pin_id, {})
            .get("videos", {})
            .get("video_list", {})
            .get("V_720P", {})
            .get("url", None)
        )
    except Exception as excp:
        video_url = None
    if not video_url:
        video_url = extract_story(json_load)
    return video_url


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
        pin_id: str = next(iter(json_load["pins"]))
        img_url: str = (
            json_load.get("pins", {})
            .get(pin_id, {})
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


def get_url(url: str) -> Tuple[str, Optional[str]]:
    """Extracts image and video url

    Parameters
    ----------
    url : str
        url to be crawled

    Returns
    -------
    Tuple[str, Optional[str]]
        A tuple containing image url and video url if present.
    """
    json_load, og_image_url = scrap_url(url)
    image_url = extract_image(json_load) or og_image_url
    video_url = extract_video(json_load)
    try:
        rdb.set(url, json.dumps({"image": image_url, "video": video_url}))
        rdb.expire(url, 3600)
    except Exception as e:
        logging.warn(e)
    return image_url, video_url


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
        try:
            cached_url = rdb.get(url)
        except Exception as e:
            logging.warn(e)
            cached_url = None
        if not cached_url:
            image_url, video_url = get_url(url)
        else:
            cached_url = json.loads(cached_url)
            image_url = cached_url.get("image")
            video_url = cached_url.get("video")
            if not video_url:
                image_url, video_url = get_url(url)
            else:
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
                try:
                    bot.send_photo(message.chat.id, image_url)
                except:
                    img = requests.get(image_url)
                    bot.send_photo(message.chat.id, img.content)
        else:
            bot.send_chat_action(message.chat.id, "upload_video")
            media_type = "Video"
            try:
                bot.send_video(message.chat.id, video_url)
            except apihelper.ApiException as e:
                payload = {"url": video_url, "chat_id": message.chat.id}
                resp = requests.post(
                    url=server.config["WORKER_URL"],
                    headers=server.config["WORKER_HEADERS"],
                    data=payload,
                )
                if resp.status_code == 201:
                    media_type = "Video too long"
                elif resp.status_code == 501:
                    raise Exception
        bot.send_message(
            message.chat.id,
            SUPPORT_MESSAGE,
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )
        bot.send_message(
            message.chat.id,
            f"Watch - {random.choices(server.config['YT_VIDEOS'])[0]}",
            parse_mode="MARKDOWN",
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
    logging.info("%s - requested to download %s", message.chat.id, message.text)
    url: str = extract_url(message.text)
    # adding wait time as not to hit the bot rate limits - 429 telegram API error
    # time.sleep(0.4)
    if not message.chat.id in server.config["BLOCKED_USERS"]:
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
    else:
        bot.send_chat_action(message.chat.id, "typing")
        msg_content: str = (
            f"Hi {message.from_user.first_name},\n\n"
            f"You are Blocked and cannot use the bot anymore."
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
