import os
import json
import asyncio
import threading
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from hermes_core.agent import (
    get_cfg, model_tag, chat_stream,
    ollama_list_models, ollama_pull_stream, ollama_delete_model,
    load_memory, save_memory, list_skills, save_skill, get_skill,
    append_memory, MEMORY_FILE, SKILLS_DIR
)

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ─────────────────────────────────────────────────────────────────
# CONFIG API
# ─────────────────────────────────────────────────────────────────
@app.route("/api/config")
def api_config():
    cfg = get_cfg()
    safe = {}
    for k, v in cfg.items():
        if k.endswith(("_token", "_key")) and v:
            safe[k] = "***set***"
        else:
            safe[k] = v
    safe["model_tag"] = model_tag(cfg)
    return jsonify(safe)

# ─────────────────────────────────────────────────────────────────
# CHAT API (streaming SSE)
# ─────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    messages = data.get("messages", [])
    cfg = get_cfg()

    def generate():
        yield from chat_stream(messages, cfg)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# ─────────────────────────────────────────────────────────────────
# OLLAMA / MODELS API
# ─────────────────────────────────────────────────────────────────
@app.route("/api/models")
def api_models():
    cfg = get_cfg()
    models = ollama_list_models(cfg["ollama_host"])
    return jsonify({"models": models, "current": model_tag(cfg)})

@app.route("/api/models/pull", methods=["POST"])
def api_pull():
    data = request.json or {}
    model = data.get("model", "")
    cfg = get_cfg()
    if not model:
        model = model_tag(cfg)

    def generate():
        yield from ollama_pull_stream(model, cfg["ollama_host"])

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.route("/api/models/delete", methods=["POST"])
def api_delete_model():
    data = request.json or {}
    model = data.get("model", "")
    cfg = get_cfg()
    result = ollama_delete_model(model, cfg["ollama_host"])
    return jsonify(result)

@app.route("/api/ollama/status")
def api_ollama_status():
    cfg = get_cfg()
    models = ollama_list_models(cfg["ollama_host"])
    return jsonify({
        "online": len(models) >= 0,
        "host": cfg["ollama_host"],
        "model_count": len(models),
        "current_model": model_tag(cfg)
    })

# Popular HuggingFace GGUF models for quick-pick
@app.route("/api/hf/popular")
def api_hf_popular():
    popular = [
        {"id": "bartowski/Llama-3.2-1B-Instruct-GGUF",   "quants": ["Q4_K_M","Q8_0","IQ3_M"], "size": "1B",  "desc": "Fast, lightweight"},
        {"id": "bartowski/Llama-3.2-3B-Instruct-GGUF",   "quants": ["Q4_K_M","Q8_0","IQ3_M"], "size": "3B",  "desc": "Balanced speed/quality"},
        {"id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "quants": ["Q4_K_M","Q5_K_M","Q8_0"], "size": "8B", "desc": "High quality"},
        {"id": "bartowski/Mistral-7B-Instruct-v0.3-GGUF","quants": ["Q4_K_M","Q5_K_M","Q8_0"], "size": "7B",  "desc": "Mistral v0.3"},
        {"id": "bartowski/gemma-2-2b-it-GGUF",            "quants": ["Q4_K_M","Q8_0"],           "size": "2B",  "desc": "Google Gemma 2"},
        {"id": "bartowski/Phi-3.5-mini-instruct-GGUF",   "quants": ["Q4_K_M","Q8_0"],           "size": "3.8B","desc": "Microsoft Phi-3.5"},
        {"id": "mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF", "quants": ["Q4_K_M","Q8_0"], "size": "8B", "desc": "Uncensored Llama"},
        {"id": "arcee-ai/SuperNova-Medius-GGUF",          "quants": ["Q4_K_M","Q8_0"],           "size": "14B", "desc": "SuperNova Medius"},
        {"id": "bartowski/Qwen2.5-7B-Instruct-GGUF",     "quants": ["Q4_K_M","Q5_K_M","Q8_0"], "size": "7B",  "desc": "Qwen 2.5"},
        {"id": "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF","quants":["Q4_K_M","Q8_0"],         "size": "7B",  "desc": "DeepSeek R1 Distill"},
    ]
    return jsonify(popular)

# ─────────────────────────────────────────────────────────────────
# MEMORY API
# ─────────────────────────────────────────────────────────────────
@app.route("/api/memory", methods=["GET"])
def api_memory_get():
    return jsonify({"memory": load_memory()})

@app.route("/api/memory", methods=["POST"])
def api_memory_post():
    data = request.json or {}
    content = data.get("content", "")
    save_memory(content)
    return jsonify({"ok": True})

@app.route("/api/memory/append", methods=["POST"])
def api_memory_append():
    data = request.json or {}
    note = data.get("note", "")
    append_memory(note)
    return jsonify({"ok": True})

@app.route("/api/memory/clear", methods=["POST"])
def api_memory_clear():
    save_memory("")
    return jsonify({"ok": True})

# ─────────────────────────────────────────────────────────────────
# SKILLS API
# ─────────────────────────────────────────────────────────────────
@app.route("/api/skills", methods=["GET"])
def api_skills_list():
    return jsonify(list_skills())

@app.route("/api/skills/<name>", methods=["GET"])
def api_skill_get(name):
    content = get_skill(name)
    if content is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"name": name, "content": content})

@app.route("/api/skills/<name>", methods=["POST", "PUT"])
def api_skill_save(name):
    data = request.json or {}
    content = data.get("content", "")
    save_skill(name, content)
    return jsonify({"ok": True})

@app.route("/api/skills/<name>", methods=["DELETE"])
def api_skill_delete(name):
    from pathlib import Path
    path = SKILLS_DIR / f"{name}.md"
    if path.exists():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

# ─────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "hermesbot"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
