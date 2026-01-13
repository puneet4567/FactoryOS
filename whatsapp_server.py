from fastapi import FastAPI, Form, Response
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import whisper
import os
import requests

app = FastAPI()

# Load Voice Model (Tiny is faster for Docker)
print("👂 Loading Whisper Model...")
ear_model = whisper.load_model("tiny") 

# Safety Lock
PENDING_ACTIONS = {}

# Connect to Ollama (Docker-aware)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
client = ollama.Client(host=OLLAMA_HOST)

async def ask_factory_brain(user_query: str, sender_id: str):
    # 1. Check for Confirmations
    if sender_id in PENDING_ACTIONS:
        pending = PENDING_ACTIONS[sender_id]
        if user_query.lower().strip() in ["yes", "confirm", "ok"]:
            action, args = pending['tool'], pending['args']
            del PENDING_ACTIONS[sender_id]
            # Re-connect to execute
            server_params = StdioServerParameters(command="python", args=["server.py"], env=os.environ)
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(action, arguments=args)
                    return f"✅ EXECUTED: {result.content[0].text}"
        else:
            del PENDING_ACTIONS[sender_id]
            return "❌ Cancelled."

    # 2. Start MCP Session
    server_params = StdioServerParameters(command="python", args=["server.py"], env=os.environ)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = await session.list_tools()
            # Convert MCP tools to Ollama format
            ollama_tools = [{
                'type': 'function', 
                'function': {'name': t.name, 'description': t.description, 'parameters': t.inputSchema}
            } for t in mcp_tools.tools]

            # 3. Chat with AI
            print(f"🤖 Sending query to Ollama: {user_query}")
            response = client.chat(
                model='llama3.2', 
                messages=[{'role': 'user', 'content': user_query}], 
                tools=ollama_tools
            )
            print("🤖 Ollama response received.")

            # 4. Handle Tool Calls
            if response['message'].get('tool_calls'):
                for tool in response['message']['tool_calls']:
                    fn_name = tool['function']['name']
                    fn_args = tool['function']['arguments']
                    print(f"🛠️ Tool Call Detected: {fn_name} with {fn_args}")
                    
                    # SAFETY LOCK for Writes
                    if fn_name in ["log_production", "update_stock"]:
                         PENDING_ACTIONS[sender_id] = {"tool": fn_name, "args": fn_args}
                         return f"✋ CONFIRM: {fn_name} with {fn_args}? (Reply YES)"
                    
                    # Execute Reads Immediately
                    print(f"🚀 Executing Tool: {fn_name}...")
                    result = await session.call_tool(fn_name, arguments=fn_args)
                    print(f"✅ Tool Result: {result}")
                    return result.content[0].text
            
            print("💬 No tool calls. Returning content.")
            return response['message']['content']

@app.post("/whatsapp")
async def reply_whatsapp(Body: str = Form(None), MediaUrl0: str = Form(None), MediaContentType0: str = Form(None), From: str = Form(...)):
    user_text = Body or ""
    
    # Handle Voice
    if MediaContentType0 and "audio" in MediaContentType0:
        print(f"🎤 Voice Note from {From}: {MediaUrl0}")
        try:
            # Twilio Auth
            tw_sid = os.getenv("TWILIO_ACCOUNT_SID")
            tw_token = os.getenv("TWILIO_AUTH_TOKEN")
            auth = (tw_sid, tw_token) if tw_sid and tw_token and "PLACEHOLDER" not in tw_sid else None

            resp = requests.get(MediaUrl0, auth=auth, timeout=10) # 10s timeout
            if resp.status_code == 200 and len(resp.content) > 0:
                with open("temp.ogg", "wb") as f: f.write(resp.content)
                try:
                    user_text = ear_model.transcribe("temp.ogg", fp16=False)["text"]
                except Exception as e:
                    print(f"❌ Whisper Error: {e}")
                    user_text = "I couldn't hear that properly."
                finally:
                    if os.path.exists("temp.ogg"):
                        os.remove("temp.ogg")
            else:
                print(f"❌ Download Failed: {resp.status_code}")
                return Response(content=f"<Response><Message>❌ Audio download failed (Status {resp.status_code}). Please text me instead.</Message></Response>", media_type="application/xml")
        except Exception as e:
             print(f"❌ Network Error: {e}")
             return Response(content=f"<Response><Message>❌ Error processing audio. Please text me instead.</Message></Response>", media_type="application/xml")

    answer = await ask_factory_brain(user_text, From)
    return Response(content=f"<Response><Message>{answer}</Message></Response>", media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)