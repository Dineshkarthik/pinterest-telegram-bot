import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36"
}
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
REDIS_URL = os.getenv("REDIS_URL")
WORKER_URL = os.getenv("WORKER_URL")
WORKER_HEADERS = {"X-API-Key": os.getenv("WORKER_API_KEY")}
BLOCKED_USERS = list(map(int, os.getenv("BLOCKED_USERS").split(",")))
