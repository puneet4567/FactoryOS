from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Create dummy PDF if none exists
import os
if not os.path.exists("manual.pdf"):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas("manual.pdf")
    c.drawString(100, 750, "Error 502: Blade Jam. Solution: Apply grease.")
    c.save()

loader = PyPDFLoader("manual.pdf")
docs = loader.load()
splits = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(docs)

Chroma.from_documents(
    documents=splits,
    embedding=OllamaEmbeddings(model="nomic-embed-text"),
    persist_directory="./chroma_db"
)
print("✅ Manual Ingested!")