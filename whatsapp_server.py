# whatsapp_server.py
from fastapi import FastAPI, Form, Response
import ollama
from mcp import ClientSession, StdioServerParameters
import whisper
import os
import requests

app = FastAPI()

# LOAD THE EAR (Voice Model)
print("👂 Loading Whisper Model (This may take a minute)...")
ear_model = whisper.load_model("base") 

# SAFETY LOCK: Stores pending actions
PENDING_ACTIONS = {}

async def ask_factory_brain(user_query: str, sender_id: str):
    # 1. CHECK FOR PENDING CONFIRMATION
    if sender_id in PENDING_ACTIONS:
        pending = PENDING_ACTIONS[sender_id]
        if user_query.lower().strip() in ["yes", "ok", "confirm", "haan"]:
            # EXECUTE THE PENDING ACTION (Simulated for safety)
            action = pending['tool']
            args = pending['args']
            del PENDING_ACTIONS[sender_id]
            # IN REALITY: Call await session.call_tool(action, args) here
            return f"✅ APPROVED. Executed '{action}' with data: {args}"
        
        elif user_query.lower().strip() in ["no", "cancel", "stop"]:
            del PENDING_ACTIONS[sender_id]
            return "❌ Cancelled."

    # 2. CONNECT TO MCP SERVER
    server_params = StdioServerParameters(command="python", args=["server.py"], env=None)
    
    async with ClientSession(server_params) as session:
        await session.initialize()
        mcp_tools = await session.list_tools()
        ollama_tools = [{'type': 'function', 'function': {'name': t.name, 'description': t.description, 'parameters': t.inputSchema}} for t in mcp_tools.tools]

        # 3. CHAT WITH LLAMA
        messages = [{'role': 'system', 'content': 'You are a Factory Assistant. Keep answers short.'}, {'role': 'user', 'content': user_query}]
        response = ollama.chat(model='llama3.1', messages=messages, tools=ollama_tools)

        # 4. HANDLE TOOL CALLS
        if response['message'].get('tool_calls'):
            for tool in response['message']['tool_calls']:
                fn_name = tool['function']['name']
                fn_args = tool['function']['arguments']
                
                # SAFETY INTERCEPT FOR WRITES
                if fn_name in ["log_production", "update_stock"]:
                     PENDING_ACTIONS[sender_id] = {"tool": fn_name, "args": fn_args}
                     return f"✋ WAIT. You want to {fn_name} with {fn_args}. Reply 'YES' to confirm."
                
                # EXECUTE READS IMMEDIATELY
                result = await session.call_tool(fn_name, arguments=fn_args)
                return result.content[0].text # Return raw tool output

        return response['message']['content']

@app.post("/whatsapp")
async def reply_whatsapp(Body: str = Form(None), MediaUrl0: str = Form(None), MediaContentType0: str = Form(None), From: str = Form(...)):
    user_text = Body
    
    # HANDLE VOICE NOTES
    if MediaContentType0 and "audio" in MediaContentType0:
        print("🎤 Voice Note Received.")
        audio_data = requests.get(MediaUrl0).content
        with open("temp.ogg", "wb") as f: f.write(audio_data)
        user_text = ear_model.transcribe("temp.ogg")["text"]
        os.remove("temp.ogg")

    answer = await ask_factory_brain(user_text, From)
    return Response(content=f"<Response><Message>{answer}</Message></Response>", media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)