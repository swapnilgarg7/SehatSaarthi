from flask import Flask, request
import os
import requests
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv(override=True)

# Environment variables
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")
GRAPH_URL = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Temporary session to track user states
user_state = {}  # {wa_id: 'awaiting_name'}

# Helper to send message
def send_message(to, text):
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": text
        }
    }
    response = requests.post(GRAPH_URL, headers=HEADERS, json=data)
    print("Send response:", response.status_code, response.json())

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Received:", data)

    if data.get("entry"):
        for entry in data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    if messages:
                        message = messages[0]
                        wa_id = message["from"]
                        msg_text = message["text"]["body"].strip().lower()

                        # Check if user already in session
                        if user_state.get(wa_id) == "awaiting_name":
                            send_message(wa_id, f"Hi {message['text']['body']} 👋")
                            user_state.pop(wa_id)  # Clear state
                        elif msg_text == "hi":
                            send_message(wa_id, "Hey! What’s your name?")
                            user_state[wa_id] = "awaiting_name"
                        else:
                            send_message(wa_id, "Say 'hi' to start 😊")

    return "OK", 200

# GET route for verification
@app.route("/webhook", methods=["GET"])
def verify():
    VERIFY_TOKEN = "my_secret_token"  # Replace with your verify token
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

if __name__ == "__main__":
    app.run(port=8000)
