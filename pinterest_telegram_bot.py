import os
import json
import logging

import redis
import requests
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
    """Base class for other exceptions"""

    pass


def read_url(_url: str) -> BeautifulSoup:
    r = requests.get(
        _url, headers=server.config["HEADERS"], allow_redirects=True
    )
    resp = requests.get(
        r.url.split("/sent")[0],
        headers=server.config["HEADERS"],
        allow_redirects=True,
    )
    return BeautifulSoup(resp.text, features="html.parser")


def extract_video(json_load: dict) -> tuple:
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


def extract_image(json_load: dict) -> str:
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
def download_image(message):
    """/download."""
    text = "Please reply with the Pinterest URL to download image/video."
    bot.send_chat_action(message.chat.id, "typing")
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, send_image)


def send_image(message):
    try:
        url: str = message.text
        logging.info("%s - requested to download %s", message.chat.id, url)
        if not url.startswith("http"):
            raise InvalidUrlError(f"'{url}' not a valid url")
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
                        f"Please download video from the [here]({video_url})"
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
    except Exception as e:
        error_message = (
            f"Internal Error occured when downloading - {url}.\n"
            "For support contact - [Pinterest Downloader Support Channel](https://t.me/joinchat/F-YaLRcPqF-__BdvLoSB7Q)"
        )
        logging.error(e)
        bot.send_message(
            message.chat.id,
            error_message,
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )


@bot.message_handler(commands=["start", "help"])
def send_instructions(message):
    """/start, /help"""
    bot.send_chat_action(message.chat.id, "typing")
    msg_content: str = (
        "*Available commands:*\n\n"
        "/download - downloads pinterest images\n"
        "To see how to download this video - https://youtu.be/b7ctyUvwzno"
    )
    bot.send_message(
        message.chat.id,
        msg_content,
        parse_mode="markdown",
    )


@bot.message_handler(func=lambda m: True)
def default_message(message):
    bot.send_chat_action(message.chat.id, "typing")
    msg_content: str = (
        "Hi,\n\nPlease use /download command to download.\n"
        "Use /help to get assistance with downloading."
    )
    bot.send_message(
        message.chat.id,
        msg_content,
        parse_mode="markdown",
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
