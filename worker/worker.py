import os
import requests
from flask import Flask, request
from telebot import TeleBot, types, apihelper


bot = TeleBot(os.environ.get("BOT_TOKEN"))

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return "True", 200


@app.route("/send", methods=["post"])
def send():
    try:
        video = requests.get(request.form["url"])
        bot.send_video(request.form["chat_id"], video.content)
        return_value = "True", 200
    except apihelper.ApiException as e:
        media_type = "Video too large"
        bot.send_message(
            request.form["chat_id"],
            (
                "Unable to send video here in chat this may be due to "
                "Telegram Bots API send file [size limitation](https://core.telegram.org/bots/api#sending-files)\n"
                "the video is too large for the bot to share here.\n"
                f"*Please download video from* [here]({request.form['url']})"
            ),
            parse_mode="MARKDOWN",
            disable_web_page_preview=True,
        )
        return_value = "True", 201
    except Exception:
        return_value = "False", 501
    return return_value


if __name__ == "__main__":
    app.run()