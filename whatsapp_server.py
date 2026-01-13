from fastapi import FastAPI, Form, Response, BackgroundTasks
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
                tool_output = result.content[0].text
                print(f"✅ Tool Result: {tool_output}")

                # Feed back to LLM for natural language response
                messages = [
                    {'role': 'system', 'content': 'You are a factory assistant. Answer the user question using ONLY the provided Tool Output below. Do not use outside knowledge. If the answer is in the tool output, repeat it exactly.'},
                    {'role': 'user', 'content': user_query},
                    response['message'],
                    {'role': 'tool', 'content': tool_output}
                ]
                
                final_response = client.chat(
                    model='llama3.2',
                    messages=messages,
                )
                return final_response['message']['content']
            
            print("💬 No tool calls. Returning content.", flush=True)
            return response['message']['content']

async def process_ai_response(user_text: str, sender_id: str):
    print(f"🔄 Processing AI response for {sender_id}...", flush=True)
    try:
        answer = await ask_factory_brain(user_text, sender_id)
        print(f"✅ AI Answer Ready: {answer[:50]}...", flush=True)
    except Exception as e:
        print(f"❌ AI Processing Failed: {e}", flush=True)
        return

    # Send final answer via Twilio API (since we already replied to webhook)
    tw_sid = os.getenv("TWILIO_ACCOUNT_SID")
    tw_token = os.getenv("TWILIO_AUTH_TOKEN")
    if tw_sid and tw_token:
        try:
            client = requests.auth.HTTPBasicAuth(tw_sid, tw_token)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{tw_sid}/Messages.json"
            data = {"To": sender_id, "From": "whatsapp:+14155238886", "Body": answer}
            resp = requests.post(url, auth=client, data=data) 
            print(f"✅ Sent async response to {sender_id}. Status: {resp.status_code}", flush=True)
            if resp.status_code != 201:
                print(f"⚠️ Twilio API Error: {resp.text}", flush=True)
        except Exception as e:
            print(f"❌ Failed to send async response: {e}", flush=True)

@app.post("/whatsapp")
async def reply_whatsapp(background_tasks: BackgroundTasks, Body: str = Form(None), MediaUrl0: str = Form(None), MediaContentType0: str = Form(None), From: str = Form(...)):
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

    # Start AI in background to avoid Twilio 15s timeout
    background_tasks.add_task(process_ai_response, user_text, From)
    return Response(content=f"<Response><Message>🧠 Thinking...</Message></Response>", media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)