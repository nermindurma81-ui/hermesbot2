from flask import Flask, render_template, request, jsonify
import os
import sys
import logging
from telegram_bot import telegram_bp, telegram_bot

# Add hermes_core to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hermes_core.agent import HermesAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Register Telegram blueprint
app.register_blueprint(telegram_bp, url_prefix='/telegram')

# Config
PORT = int(os.environ.get("PORT", 7860))
HF_MODEL = os.environ.get("HF_MODEL", 'bartowski/Llama-3.2-1B-Instruct-GGUF')
HF_QUANT = os.environ.get("HF_QUANT", 'Q4_K_M')
BOT_NAME = os.environ.get("BOT_NAME", 'Hermes')
MEMORY_ENABLED = os.environ.get("MEMORY_ENABLED", 'true').lower() == 'true'
MAX_CONTEXT_MESSAGES = int(os.environ.get("MAX_CONTEXT_MESSAGES", 20))

# Initialize agent
agent = HermesAgent()

@app.route('/')
def index():
    return render_template('index.html', bot_name=BOT_NAME)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    def generate():
        try:
            for chunk in agent.chat_stream(message):
                yield chunk
        except Exception as e:
            logger.error(f"Chat error: {e}")
            yield f"Error: {str(e)}"
    
    return app.response_class(generate(), mimetype='text/plain')

@app.route('/api/models', methods=['GET'])
def list_models():
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags')
        return jsonify(response.json())
    except:
        return jsonify({'models': []})

@app.route('/api/pull', methods=['POST'])
def pull_model():
    data = request.get_json()
    model = data.get('model', '')
    quant = data.get('quant', '')
    
    if not model or not quant:
        return jsonify({'error': 'Missing model or quant'}), 400
    
    full_model = f"hf.co/{model}:{quant}"
    
    def generate():
        import requests
        try:
            response = requests.post(
                'http://localhost:11434/api/pull',
                json={'name': full_model},
                stream=True
            )
            for line in response.iter_lines():
                if line:
                    yield line.decode('utf-8') + '\n'
        except Exception as e:
            yield f'{{"error": "{str(e)}"}}\n'
    
    return app.response_class(generate(), mimetype='application/json')

@app.route('/api/memory', methods=['GET'])
def get_memory():
    try:
        memory = agent.recall_memory("")
        return jsonify({'memory': memory})
    except:
        return jsonify({'memory': ''})

@app.route('/api/memory/clear', methods=['POST'])
def clear_memory():
    try:
        agent.memory = []
        return jsonify({'success': True})
    except:
        return jsonify({'success': False})

@app.route('/api/status', methods=['GET'])
def status():
    try:
        import requests
        response = requests.get('http://localhost:11434/api/version', timeout=2)
        return jsonify({'ollama': 'running', 'version': response.json()})
    except:
        return jsonify({'ollama': 'offline'})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)