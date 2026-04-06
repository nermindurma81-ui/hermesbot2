import os
import logging
from flask import Blueprint, request, jsonify
import requests
from hermes_core.agent import HermesAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
HF_SPACE_URL = os.environ.get("SPACE_HOST_URL")

telegram_bp = Blueprint('telegram', __name__)

class TelegramBot:
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.agent = HermesAgent()
        
    def set_webhook(self, space_url):
        if not self.token or not space_url:
            return False
        webhook_url = f"{space_url}/telegram/webhook"
        requests.get(f"{self.base_url}/deleteWebhook")
        response = requests.post(f"{self.base_url}/setWebhook", json={"url": webhook_url})
        return response.json().get("ok", False)
    
    def send_message(self, chat_id, text):
        if not text or not self.token:
            return
        if len(text) > 4000:
            text = text[:4000] + "..."
        requests.post(f"{self.base_url}/sendMessage", 
                     json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    
    def process_update(self, update):
        if "message" not in update:
            return
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd == "/start":
                self.send_message(chat_id, f"🤖 {os.environ.get('BOT_NAME', 'Hermes')} spreman!")
            elif cmd == "/clear":
                self.agent.memory = []
                self.send_message(chat_id, "🧹 Memorija očišćena!")
            return
        
        if not text:
            return
            
        try:
            response = ""
            for chunk in self.agent.chat_stream(text):
                response += chunk
            self.send_message(chat_id, response)
        except Exception as e:
            logger.error(f"Error: {e}")
            self.send_message(chat_id, "❌ Greška")

telegram_bot = TelegramBot()

@telegram_bp.route('/webhook', methods=['POST'])
def webhook():
    telegram_bot.process_update(request.get_json())
    return jsonify({"ok": True})

@telegram_bp.route('/setup', methods=['GET'])
def setup():
    if telegram_bot.set_webhook(HF_SPACE_URL):
        return jsonify({"ok": True})
    return jsonify({"error": "Failed"}), 500