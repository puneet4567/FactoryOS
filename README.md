# 🏭 FactoryOS - AI-Powered Factory Assistant

FactoryOS is an intelligent, voice-activated factory management system that runs locally using Docker. It integrates **WhatsApp (Twilio)**, **Ollama (Llama 3.2)**, **Wait-for-it (MCP)**, and a **Streamlit Dashboard** to allow factory owners to log production and manage inventory via voice notes or text.

## 🚀 Features
- **Voice-to-Action**: Send voice notes on WhatsApp ("Log 50 rolls produced") -> Transcribed by Whisper -> Processed by Llama 3 -> Executed in Database.
- **Fast & Optimized**: Runs on **Llama 3.2 (3B)** for rapid CPU inference. Pre-warms model on startup.
- **Smart Tools (MCP)**: The AI has tools to `log_production`, `update_stock`, and `analyze_data`.
- **Real-time Dashboard**: Streamlit interface to visualize production trends and logs.
- **Self-Healing**: Robust error handling for audio downloads and network issues.
- **Secure**: Credentials managed via `.env` file.

## 🛠️ Prerequisites
- **Docker Desktop**: [Install Docker](https://www.docker.com/products/docker-desktop/)
- **Ngrok**: For exposing the local WhatsApp server to Twilio. [Install Ngrok](https://ngrok.com/download)
- **Twilio Account**: For WhatsApp Sandbox. [Sign up](https://www.twilio.com/)

## 📦 Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/FactoryOS.git
   cd FactoryOS
   ```

2. **Configure Credentials**
   Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and paste your Twilio credentials:
   ```ini
   TWILIO_ACCOUNT_SID=ACxxxxxxxx...
   TWILIO_AUTH_TOKEN=xxxxxxx...
   ```

## 🏃‍♂️ Running the Application

1. **Start the Docker Stack**
   ```bash
   docker-compose up --build
   ```
   *This starts Ollama (AI), Postgres (DB), and the FactoryOS App.*

   > **⚠️ First Run Note**: The first time you run this, Ollama will download the **Llama 3.2** model (~2GB). This takes 2-3 minutes.
   > Watch the logs: `docker-compose logs -f ollama`. 
   > When you see `✅ Pre-warm request sent` in the `factory_os` logs, it is ready!

2. **Start Ngrok**
   Expose port 8000 to the internet:
   ```bash
   ngrok http 8000
   ```
   Copy the HTTPS URL (e.g., `https://1234-56-78.ngrok-free.app`).

3. **Configure Twilio**
   - Go to [Twilio Console > Messaging > Try it out > Send a WhatsApp message](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn).
   - **Sandbox Settings**: Set "When a message comes in" to:
     `YOUR_NGROK_URL/whatsapp` (e.g., `https://1234-56-78.ngrok-free.app/whatsapp`)

## 📱 Usage

### WhatsApp Bot
Send commands to your Twilio Sandbox number:
- **Text**: "Log 100 rolls for Machine A"
- **Voice**: *Record a voice note saying "Add 50 logs to inventory"*
- **Validation**: If the intention is critical (log/update), the bot will ask for confirmation (Yes/No).

### Command Center (Dashboard)
Access the local dashboard to view live data:
- **URL**: [http://localhost:8501](http://localhost:8501)
- Shows daily production charts and logs.

## 📂 Project Structure
- `whatsapp_server.py`: FastAPI server handling WhatsApp webhooks, audio transcription (Whisper), and AI logic (Ollama+MCP).
- `server.py`: MCP Server defining tools (`log_production`, `update_stock`) and database interactions.
- `dashboard.py`: Streamlit app for visualization.
- `start.sh`: Startup script that launches services and handles model pre-warming.
- `docker-compose.yml`: Orchestration for App, DB, and Ollama.

## 🔧 Troubleshooting
- **Audio Download Failed (401)**: Ensure `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are valid in `.env` and you have restarted the container.
- **Slow First Response**: The AI model loads lazily. We added a pre-warm script, but if it's the very first run, it might still be downloading the model. Check `docker-compose logs -f ollama`.
- **Database Connection**: The app uses `db` host internally (port 5432) and maps to `localhost:5435` externally to avoid conflicts.
- **Pre-warm Errors**: If you see DNS errors in `start.sh`, the retry logic usually fixes it after 5-10 seconds.