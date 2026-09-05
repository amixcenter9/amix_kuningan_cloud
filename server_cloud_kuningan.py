from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json
import uuid

app = FastAPI(title="SIAGA KUNINGAN - FIX SESSION_ID")

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
@app.get("/xiaozhi/ota")
@app.post("/xiaozhi/ota")
async def ota(request: Request):
    return JSONResponse({
        "firmware": {"version": "2.4.2-amix-kuningan", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/", "token": ""},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/")
def root():
    return {"status": "Siaga Online - FIX SESSION_ID", "fix": "session_id added"}

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    print(f">>> SIAGA KONEK! session_id={session_id}")

    # HELLO WAJIB ADA session_id + transport + audio_params sample_rate 24000
    hello = {
        "type": "hello",
        "transport": "websocket",
        "session_id": session_id,
        "audio_params": {
            "format": "opus",
            "sample_rate": 24000,
            "channels": 1,
            "frame_duration": 60
        }
    }
    await websocket.send_text(json.dumps(hello))
    print(f"<<< Kirim hello dengan session_id")

    while True:
        try:
            data = await websocket.receive()
            if "bytes" in data:
                continue
            if "text" in data:
                try:
                    msg = json.loads(data["text"])
                    print(f"Dari Siaga [{session_id}]: {msg}")

                    if msg.get("type") == "hello":
                        # Balas hello lagi dengan session_id yang sama
                        await websocket.send_text(json.dumps(hello))

                    # Semua mode: detect, start, stop
                    if msg.get("type") == "listen":
                        state = msg.get("state")
                        print(f"Listen state: {state}")
                        # Kalau client bilang detect atau stop, kita jawab
                        if state in ["detect", "stop", "start"]:
                            # Kalau detect, kadang ada text wake word
                            reply = "Kumaha bos! Abdi Siaga ti Kuningan! Akhirna konek! Kumaha kabarna bos?"
                            
                            # Kirim TTS sesuai protokol resmi (pakai session_id)
                            await websocket.send_text(json.dumps({
                                "type": "tts",
                                "state": "start",
                                "session_id": session_id
                            }))
                            await websocket.send_text(json.dumps({
                                "type": "tts",
                                "state": "sentence_start",
                                "text": reply,
                                "session_id": session_id
                            }))
                            # Kalau mau pakai audio opus asli, kirim binary di sini
                            # Untuk sekarang text only biar OLED muncul teks
                            await websocket.send_text(json.dumps({
                                "type": "tts",
                                "state": "sentence_end",
                                "session_id": session_id
                            }))
                            await websocket.send_text(json.dumps({
                                "type": "tts",
                                "state": "stop",
                                "session_id": session_id
                            }))
                            print(f"Jawab terkirim!")

                    if msg.get("type") == "text":
                        user_text = msg.get("text", "")
                        print(f"User text: {user_text}")
                        reply = f"Siap bos! Bos bilang {user_text} ya? Abdi ngadangu!"
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply, "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))

                except Exception as e:
                    print(f"Error parsing: {e}")
                    pass
        except Exception as e:
            print(f"Disconnect {session_id}: {e}")
            break
