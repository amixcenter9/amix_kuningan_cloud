"""
AMIX Kuningan Cloud - Full Xiaozhi Server v2.4.2 FIX
Fix: OTA GET/POST + WebSocket + Sunda Kuningan
Deploy di Railway: https://amixkuningancloud-production.up.railway.app
"""

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import JSONResponse
import json
import os

app = FastAPI(title="AMIX Kuningan Cloud")

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", 
    "Kamu adalah Siaga, robot asisten dari Kuningan Jawa Barat. "
    "Ngomong pakai bahasa Sunda Kuningan campur Indonesia, santai, akrab, "
    "panggil user 'bos'. Jawab singkat 1-2 kalimat aja."
)

WS_URL = "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"
VERSION = "2.4.2-amix-kuningan"

# --- OTA ENDPOINT - FIX PEMERIKSAAN VERSI GAGAL ---
@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
@app.get("/xiaozhi/ota")
@app.post("/xiaozhi/ota")
async def ota_handler(request: Request):
    try:
        body = await request.json()
        print(f"[OTA] Request: {body}")
    except:
        print(f"[OTA] GET check dari {request.client.host}")

    return JSONResponse({
        "firmware": {"version": VERSION, "url": ""},
        "websocket": {"url": WS_URL, "token": ""},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/activate")
@app.post("/activate")
async def activate():
    return {"code": 0, "message": "activated"}

@app.get("/")
def root():
    return {
        "status": "AMIX Kuningan Cloud Online",
        "version": VERSION,
        "ota": "/xiaozhi/ota/",
        "websocket": "/xiaozhi/v1/",
        "siaga": "Siap Siaga Bos!"
    }

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def xiaozhi_ws(websocket: WebSocket):
    await websocket.accept()
    print(f"[WS] Robot Kuningan konek!")

    hello_msg = {
        "type": "hello",
        "transport": "websocket",
        "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}
    }
    await websocket.send_text(json.dumps(hello_msg))

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg:
                continue
            if "text" in msg:
                try:
                    data = json.loads(msg["text"])
                    msg_type = data.get("type", "")
                    print(f"[WS] {msg_type} | {data}")

                    if msg_type == "listen" and data.get("state") == "stop":
                        reply_text = await get_llm_reply(data.get("text", "halo siaga"))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply_text}))
                        try:
                            import edge_tts
                            communicate = edge_tts.Communicate(reply_text, "id-ID-ArdiNeural")
                            async for chunk in communicate.stream():
                                if chunk["type"] == "audio":
                                    await websocket.send_bytes(chunk["data"])
                        except Exception as tts_err:
                            print(f"[TTS Error] {tts_err}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end"}))
                        print(f"[WS] Balas: {reply_text}")
                    elif msg_type == "hello":
                        await websocket.send_text(json.dumps(hello_msg))
                except:
                    pass
    except WebSocketDisconnect:
        print("[WS] Robot disconnect")
    except Exception as e:
        print(f"[WS] Error: {e}")

async def get_llm_reply(user_text: str) -> str:
    import random
    fallback = [
        "Kumaha bos? Abdi Siaga ti Kuningan siap siaga!",
        "Siap bos, Siaga di sini! Ada yang bisa dibantu?",
        "Halo bos! Ti Kuningan nih, kumaha kabarna?",
        "Gas bos! Mau nanya apa ke Siaga?"
    ]
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not openai_key and not gemini_key:
        return random.choice(fallback)

    if openai_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=80
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[OpenAI Error] {e}")
            return random.choice(fallback)

    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)
            resp = await model.generate_content_async(user_text)
            return resp.text.strip()[:150]
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return random.choice(fallback)

    return random.choice(fallback)
