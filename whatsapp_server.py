from fastapi import FastAPI, Form, Response, BackgroundTasks
import whisper
import os
import requests

app = FastAPI()

# Load Voice Model (Tiny is faster for Docker)
print("👂 Loading Whisper Model...")
ear_model = whisper.load_model("tiny") 


from agent_graph import graph

async def process_ai_response(user_text: str, sender_id: str):
    print(f"🔄 Processing AI response for {sender_id} via LangGraph...", flush=True)
    try:
        # Create Thread ID specific to user for memory
        config = {"configurable": {"thread_id": sender_id}}
        
        # Invoke Graph
        # The graph expects a list of messages
        last_message = None
        async for event in graph.astream({"messages": [("user", user_text)]}, config):
            for value in event.values():
                if value and "messages" in value:
                    msg = value["messages"][-1]
                    content = None
                    if hasattr(msg, "content"):
                        content = msg.content
                    else:
                        content = msg.get("content", str(msg))
                    
                    if content and str(content).strip():
                        last_message = content
                        print(f"🤖 Graph Step: {last_message[:50]}...", flush=True)
        
        answer = last_message if last_message else "Internal Error: No response from Supervisor."
        
        print(f"✅ AI Answer Ready: {answer[:50]}...", flush=True)
    except Exception:
        import traceback
        print(f"❌ AI Processing Failed:\n{traceback.format_exc()}", flush=True)
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
                    print(f"📝 Transcribed Text: '{user_text}'", flush=True)
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