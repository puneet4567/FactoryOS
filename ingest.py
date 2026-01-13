from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Create dummy PDF if none exists
import os
import requests

# 1. Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# 2. Ensure Embedding Model Exists
print(f"🔌 Connecting to Ollama at {OLLAMA_HOST}...")
try:
    requests.post(f"{OLLAMA_HOST}/api/pull", json={"name": "nomic-embed-text"})
    print("⬇️  Pulled 'nomic-embed-text' model.")
except Exception as e:
    print(f"⚠️ Warning: Could not pull model automatically: {e}")

# 3. Create dummy file if missing
if not os.path.exists("manual.pdf"):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas("manual.pdf")
    c.drawString(100, 750, "Error 502: Blade Jam. Solution: Apply grease.")
    c.save()
    print("📄 Created dummy 'manual.pdf'")

loader = PyPDFLoader("manual.pdf")
docs = loader.load()
splits = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(docs)

print("🧠 Ingesting...")
Chroma.from_documents(
    documents=splits,
    embedding=OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST),
    persist_directory="./chroma_db"
)
print("✅ Manual Ingested! Vector DB saved to ./chroma_db")