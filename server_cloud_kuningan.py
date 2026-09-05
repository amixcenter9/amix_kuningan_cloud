from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json

app = FastAPI()

# --- OTA WAJIB ---
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
    return {"status": "Siaga Online", "ws": "/xiaozhi/v1/"}

# --- WEBSOCKET YANG BENER (FIX TIDAK DAPAT TERHUBUNG) ---
@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    print(">>> SIAGA KONEK!")

    # KIRIM HELLO BALIK (WAJIB ADA audio_params)
    hello = {
        "type": "hello",
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16000,
            "channels": 1,
            "frame_duration": 60
        }
    }
    await websocket.send_text(json.dumps(hello))

    while True:
        try:
            data = await websocket.receive()
            # Kalau robot kirim audio (bytes)
            if "bytes" in data:
                continue
            
            # Kalau robot kirim JSON text
            if "text" in data:
                try:
                    msg = json.loads(data["text"])
                    print(f"Dari Siaga: {msg}")

                    # Robot bilang hello
                    if msg.get("type") == "hello":
                        await websocket.send_text(json.dumps(hello))
                    
                    # Robot selesai ngomong -> kita jawab
                    if msg.get("type") == "listen" and msg.get("state") == "stop":
                        reply = "Kumaha bos! Abdi Siaga ti Kuningan! Server udah konek bos! Akhirnya bisa ngobrol!"
                        print(f"Jawab: {reply}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": reply}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                except:
                    pass
        except Exception as e:
            print(f"Disconnect: {e}")
            break
