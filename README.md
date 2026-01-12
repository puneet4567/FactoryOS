# 🏭 FactoryOS: The "Brain" for Manufacturing

**Author:** Puneet Agarwal (Industrial AI Architect)  
**Status:** Live Production (Krafix Tapes)

## 📌 Overview
FactoryOS is a privacy-first Industrial AI stack that runs entirely on a MacBook M4 (Local Edge). It connects legacy manufacturing machines and manual workflows to a central "Digital Brain" using AI Agents.

## 🏗 Architecture
* **The Brain (Reasoning):** Local Llama 3.1 running on Ollama.
* **The Body (Execution):** Python MCP Server (Model Context Protocol) managing PostgreSQL.
* **The Nervous System (Input):** WhatsApp Voice Notes (via Twilio) transcribed by OpenAI Whisper (Local).
* **The Face (Visualization):** Streamlit Dashboard for real-time factory monitoring.

## 🚀 Key Features
1.  **Text-to-SQL:** Ask complex questions ("How many rolls did Slitter A make last Tuesday?") in natural language.
2.  **Voice Logging:** Workers log production data by speaking into WhatsApp.
3.  **Human-in-the-Loop Safety:** The AI cannot write to the DB (`INSERT`/`UPDATE`) without explicit 2FA confirmation from the supervisor.
4.  **Offline Privacy:** All data and AI inference stay local. No data is sent to OpenAI or Anthropic.

## 🛠 Tech Stack
* **AI:** Llama 3.1, Whisper (Base), LangGraph
* **Backend:** FastAPI, Python, PostgreSQL, MCP
* **Frontend:** Streamlit, Plotly
* **Hardware:** MacBook Pro M4, ESP32 Sensors

## 📦 Installation
1.  **Install Dependencies:** `pip install -r requirements.txt`
2.  **Start DB Server:** `python server.py`
3.  **Start WhatsApp Listener:** `python whatsapp_server.py`
4.  **Launch Dashboard:** `streamlit run dashboard.py`

Important System Requirement (For Voice)
Since we are using Whisper for voice notes, we need ffmpeg installed on your Mac, or the Python script will fail when trying to process audio.
---
*Built to demonstrate the future of Smart Manufacturing.*