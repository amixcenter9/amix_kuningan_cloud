from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json

app = FastAPI(title="SIAGA KUNINGAN - SIMPLE ANTI GAGAL")

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

@app.get("/activate")
@app.post("/activate")
async def activate():
    return {"code": 0}

@app.get("/")
def root():
    return {"status": "Siaga Kuningan Simple Online", "mode": "TEXT-ONLY-ANTI-GAGAL"}

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws(websocket: WebSocket):
    await websocket.accept()
    print("[SIAGA] Robot konek!")
    await websocket.send_text(json.dumps({
        "type": "hello",
        "transport": "websocket",
        "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1}
    }))
    while True:
        try:
            msg = await websocket.receive()
            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "listen" and data.get("state") == "stop":
                    # Jawaban fix Sunda Kuningan - PASTI NGOMONG
                    reply = "Kumaha bos! Abdi Siaga ti Kuningan, abdi ngadangu bos! Kumaha kabarna?"
                    print(f"[SIAGA] Jawab: {reply}")
                    await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": reply}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
        except Exception as e:
            print(f"[SIAGA] Disconnect: {e}")
            break
