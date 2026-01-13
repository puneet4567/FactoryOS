FROM python:3.11-slim

# 1. Install System Dependencies (ffmpeg for Voice, libpq for Postgres)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python Packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy Code
COPY . .

# 4. Start Script (Runs WhatsApp Server + Dashboard)
# Note: We do NOT run server.py here. It is launched automatically by whatsapp_server.py
RUN echo '#!/bin/bash\n\
    python whatsapp_server.py & \n\
    streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 \n\
    wait' > start.sh && chmod +x start.sh

CMD ["./start.sh"]