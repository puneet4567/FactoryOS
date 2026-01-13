#!/bin/bash
# Pre-warm the AI Model (Retry loop to handle DNS startup)
python -c "
import time, requests
for i in range(10):
    try:
        # 1. Pull the faster model first
        requests.post('http://ollama:11434/api/pull', json={'name': 'llama3.2'})
        print('⬇️ Downloading Llama 3.2...')
        
        # 2. Pre-warm (Load into RAM)
        requests.post('http://ollama:11434/api/chat', json={'model': 'llama3.2'})
        print('✅ Pre-warm request sent')
        break
    except Exception as e:
        print(f'Waiting for Ollama ({e})...')
        time.sleep(3)
" &

python whatsapp_server.py & 
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 
wait
