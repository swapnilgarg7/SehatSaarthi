import json
from dotenv import load_dotenv
import os
import requests
import aiohttp
import asyncio

# --------------------------------------------------------------
# Load environment variables
# --------------------------------------------------------------

load_dotenv(override=True)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
RECIPIENT_WAID = os.getenv("RECIPIENT_WAID")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": "Bearer " + ACCESS_TOKEN,
    "Content-Type": "application/json"
}

data = {
    "messaging_product": "whatsapp",
    "to": "917986930968",
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {
            "code": "en_US"
        }
    }
}

response = requests.post(url, headers=headers, json=data)

print("Status Code:", response.status_code)
print("Response Body:", response.json())
