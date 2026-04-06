#!/bin/bash

echo "Starting Ollama..."
ollama serve &
sleep 10

echo "Pulling model..."
ollama pull hf.co/${HF_MODEL}:${HF_QUANT} &

if [ ! -z "$TELEGRAM_BOT_TOKEN" ]; then
    (sleep 15 && curl -s http://localhost:7860/telegram/setup) &
fi

gunicorn app:app --bind 0.0.0.0:7860 --workers 2 --timeout 120