# ☤ HermesBot

AI agent web UI pokretan Ollama + HuggingFace GGUF modelima.  
Inspirisan [Hermes Agent](https://github.com/NousResearch/hermes-agent) od NousResearch.

## Features

- 🤗 **HuggingFace GGUF** — `ollama run hf.co/user/repo:quant` direktno iz UI
- 🦙 **Ollama backend** — lokalni LLM runtime, streaming odgovori
- 🧠 **Perzistentna memorija** — MEMORY.md kroz sesije
- ⚙️ **Tool loop** — `remember`, `recall_memory`, `list_skills`, `ollama_status`, `pull_model`
- 📱 **Mobile-first dark UI** — tabovi: Chat, Modeli, Connectors, Memorija
- ✈️ **Telegram / Discord** ready
- 🚂 **Railway deploy** ready

## Brzi start

```bash
# 1. Kloniraj
git clone <ovaj-repo>
cd hermesbot

# 2. Env vars
cp .env.example .env
# Uredi .env

# 3. Pokreni Ollama
ollama serve

# 4. Povuci model sa HuggingFace
ollama run hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q4_K_M

# 5. Pokreni web app
pip install -r requirements.txt
python app.py
```

## Railway Deploy

### Korak 1 — Push na GitHub
```bash
git init
git add .
git commit -m "HermesBot initial"
git remote add origin https://github.com/TVOJ_USER/hermesbot.git
git push -u origin main
```

### Korak 2 — Railway setup
1. Idi na [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → odaberi `hermesbot`
3. Dodaj **Ollama servis**:
   - New Service → Docker Image → `ollama/ollama`
   - Dodaj volume `/root/.ollama`
4. Postavi env vars:

```
OLLAMA_HOST=http://ollama.railway.internal:11434
HF_MODEL=bartowski/Llama-3.2-1B-Instruct-GGUF
HF_QUANT=Q4_K_M
BOT_NAME=HermesBot
MEMORY_ENABLED=true
PORT=5000
```

5. Deploy → otvori web URL → idi na **Modeli** tab → Pull model

### Korak 3 — Pull model na Railway Ollama
U Railway konzoli Ollama servisa:
```bash
ollama run hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q4_K_M
```
Ili kroz web UI → **Modeli** tab → odaberi model → Pull.

## Privatni HF Modeli

```bash
# 1. Kopiraj Ollama SSH key
cat ~/.ollama/id_ed25519.pub

# 2. Dodaj na https://huggingface.co/settings/keys

# 3. Sada možeš koristiti privatne modele:
ollama run hf.co/tvoj-user/privatni-model-GGUF
```

## Env Vars

| Var | Default | Opis |
|-----|---------|------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama URL |
| `HF_MODEL` | `bartowski/Llama-3.2-1B-Instruct-GGUF` | HF model repo |
| `HF_QUANT` | `Q4_K_M` | Kvantizacija |
| `BOT_NAME` | `HermesBot` | Ime bota |
| `SYSTEM_PROMPT` | `You are Hermes...` | System prompt |
| `MEMORY_ENABLED` | `true` | Memorija on/off |
| `MAX_CONTEXT_MESSAGES` | `20` | Max poruka u kontekstu |
| `TELEGRAM_BOT_TOKEN` | — | Telegram integracija |
| `DISCORD_BOT_TOKEN` | — | Discord integracija |
| `PORT` | `5000` | HTTP port |

## Arhitektura

```
hermesbot/
├── app.py              # Flask web server + API rute
├── hermes_core/
│   └── agent.py        # Hermes Agent engine
│       ├── chat_stream()    # Ollama streaming chat
│       ├── execute_tool()   # Tool loop
│       ├── load/save_memory()
│       └── list/save_skill()
├── templates/
│   └── index.html      # Mobile-first dark UI
├── memory/
│   └── MEMORY.md       # Perzistentna memorija (auto)
├── skills/
│   └── *.md            # Skillovi (auto)
├── requirements.txt
├── Procfile
├── railway.json
└── .env.example
```

## Licenca
MIT
