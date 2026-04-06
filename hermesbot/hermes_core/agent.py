"""
Hermes Agent Core
- Ollama backend with HuggingFace GGUF models (hf.co/user/repo:quant)
- Persistent memory (MEMORY.md)
- Skills system
- Agentic tool loop (web search, file ops, code exec)
- Streaming responses
"""
import os
import json
import datetime
import httpx
from pathlib import Path
from typing import Iterator, Optional

BASE_DIR = Path(__file__).parent.parent
MEMORY_FILE = BASE_DIR / "memory" / "MEMORY.md"
SKILLS_DIR  = BASE_DIR / "skills"
MEMORY_FILE.parent.mkdir(exist_ok=True)
SKILLS_DIR.mkdir(exist_ok=True)

# ── CONFIG ────────────────────────────────────────────────────────
def get_cfg():
    return {
        "ollama_host":    os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "hf_model":       os.environ.get("HF_MODEL", "bartowski/Llama-3.2-1B-Instruct-GGUF"),
        "hf_quant":       os.environ.get("HF_QUANT", "Q4_K_M"),
        "system_prompt":  os.environ.get("SYSTEM_PROMPT",
            "You are Hermes, a self-improving AI assistant. Be precise, helpful, and concise."),
        "bot_name":       os.environ.get("BOT_NAME", "Hermes"),
        "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "discord_token":  os.environ.get("DISCORD_BOT_TOKEN", ""),
        "hf_ssh_key":     os.environ.get("HF_SSH_KEY", ""),
        "memory_enabled": os.environ.get("MEMORY_ENABLED", "true").lower() == "true",
        "max_context":    int(os.environ.get("MAX_CONTEXT_MESSAGES", "20")),
    }

def model_tag(cfg: dict) -> str:
    """Build hf.co/user/repo:quant tag for Ollama."""
    model = cfg["hf_model"].strip()
    quant = cfg["hf_quant"].strip()
    if not model.startswith("hf.co/") and not model.startswith("huggingface.co/"):
        model = f"hf.co/{model}"
    return f"{model}:{quant}" if quant else model

# ── MEMORY ────────────────────────────────────────────────────────
def load_memory() -> str:
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text()
    return ""

def save_memory(content: str):
    MEMORY_FILE.write_text(content)

def append_memory(note: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    existing = load_memory()
    entry = f"\n- [{ts}] {note}"
    save_memory(existing + entry)

# ── SKILLS ────────────────────────────────────────────────────────
def list_skills() -> list[dict]:
    skills = []
    for f in SKILLS_DIR.glob("*.md"):
        content = f.read_text()
        first_line = content.split("\n")[0].lstrip("#").strip()
        skills.append({"name": f.stem, "title": first_line, "content": content})
    return skills

def get_skill(name: str) -> Optional[str]:
    path = SKILLS_DIR / f"{name}.md"
    return path.read_text() if path.exists() else None

def save_skill(name: str, content: str):
    path = SKILLS_DIR / f"{name}.md"
    path.write_text(content)

# ── TOOLS ─────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save an important note to persistent memory for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "The note to remember"}
                },
                "required": ["note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Read all saved memories.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills/procedures.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_skill",
            "description": "Create or update a skill/procedure for future use.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":    {"type": "string"},
                    "content": {"type": "string", "description": "Markdown content describing the skill"}
                },
                "required": ["name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ollama_status",
            "description": "Check Ollama connection and list available local models.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pull_model",
            "description": "Pull/download an Ollama model (supports hf.co/user/repo:quant format).",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model tag e.g. hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q4_K_M"}
                },
                "required": ["model"]
            }
        }
    }
]

def execute_tool(name: str, args: dict, cfg: dict) -> str:
    host = cfg["ollama_host"].rstrip("/")
    if name == "remember":
        append_memory(args.get("note", ""))
        return f"✅ Saved to memory: {args.get('note','')}"
    elif name == "recall_memory":
        mem = load_memory()
        return mem if mem else "No memories yet."
    elif name == "list_skills":
        skills = list_skills()
        if not skills:
            return "No skills yet."
        return "\n".join(f"- **{s['name']}**: {s['title']}" for s in skills)
    elif name == "create_skill":
        save_skill(args["name"], args["content"])
        return f"✅ Skill '{args['name']}' saved."
    elif name == "ollama_status":
        try:
            resp = httpx.get(f"{host}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            return f"✅ Ollama online at {host}\nModels: {', '.join(models) if models else 'none pulled yet'}"
        except Exception as e:
            return f"❌ Ollama unreachable at {host}: {e}"
    elif name == "pull_model":
        try:
            model = args.get("model", model_tag(cfg))
            resp = httpx.post(f"{host}/api/pull", json={"name": model}, timeout=300)
            return f"✅ Pull initiated for {model}"
        except Exception as e:
            return f"❌ Pull failed: {e}"
    return f"Unknown tool: {name}"

# ── SYSTEM PROMPT builder ─────────────────────────────────────────
def build_system(cfg: dict) -> str:
    mem = load_memory()
    skills = list_skills()
    skill_list = "\n".join(f"- {s['name']}: {s['title']}" for s in skills) or "none yet"
    memory_block = f"\n\n## Your Memory\n{mem}" if mem else ""
    return f"""{cfg['system_prompt']}

## Available Tools
You have tools: remember, recall_memory, list_skills, create_skill, ollama_status, pull_model.
Call them when appropriate by emitting a JSON tool_call block.

## Skills
{skill_list}{memory_block}

## Current Model
{model_tag(cfg)}

## Date
{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

# ── OLLAMA STREAMING CHAT ─────────────────────────────────────────
def chat_stream(messages: list, cfg: dict) -> Iterator[str]:
    """Stream chat response from Ollama, handling tool calls."""
    host = cfg["ollama_host"].rstrip("/")
    tag  = model_tag(cfg)
    system = build_system(cfg)

    payload = {
        "model": tag,
        "messages": [{"role": "system", "content": system}] + messages[-cfg["max_context"]:],
        "stream": True,
        "tools": TOOLS,
    }

    try:
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", f"{host}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = resp.text
                    yield f"data: {json.dumps({'error': f'Ollama {resp.status_code}: {body}', 'done': True})}\n\n"
                    return

                tool_calls_buffer = []
                full_content = ""

                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except:
                        continue

                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])
                    done = obj.get("done", False)

                    if content:
                        full_content += content
                        yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

                    if tool_calls:
                        tool_calls_buffer.extend(tool_calls)

                    if done:
                        # Execute any tool calls
                        if tool_calls_buffer:
                            for tc in tool_calls_buffer:
                                fn   = tc.get("function", {})
                                name = fn.get("name", "")
                                args = fn.get("arguments", {})
                                if isinstance(args, str):
                                    try: args = json.loads(args)
                                    except: args = {}
                                yield f"data: {json.dumps({'tool_call': name, 'args': args, 'done': False})}\n\n"
                                result = execute_tool(name, args, cfg)
                                yield f"data: {json.dumps({'tool_result': result, 'tool': name, 'done': False})}\n\n"

                            # Auto-save memory if long conversation
                            if cfg["memory_enabled"] and len(messages) > 10 and len(messages) % 10 == 0:
                                append_memory(f"Conversation checkpoint at {len(messages)} messages")

                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return

    except httpx.ConnectError:
        yield f"data: {json.dumps({'error': f'Cannot connect to Ollama at {host}. Is it running?', 'done': True})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

# ── OLLAMA HELPERS ────────────────────────────────────────────────
def ollama_list_models(host: str) -> list:
    try:
        resp = httpx.get(f"{host.rstrip('/')}/api/tags", timeout=5)
        return resp.json().get("models", [])
    except:
        return []

def ollama_pull_stream(model: str, host: str) -> Iterator[str]:
    try:
        with httpx.Client(timeout=600) as client:
            with client.stream("POST", f"{host.rstrip('/')}/api/pull",
                               json={"name": model}) as resp:
                for line in resp.iter_lines():
                    if line:
                        yield f"data: {line}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

def ollama_delete_model(model: str, host: str) -> dict:
    try:
        resp = httpx.delete(f"{host.rstrip('/')}/api/delete", json={"name": model}, timeout=10)
        return {"ok": resp.status_code == 200}
    except Exception as e:
        return {"error": str(e)}
