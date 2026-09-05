from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
@app.get("/xiaozhi/ota")
@app.post("/xiaozhi/ota")
async def ota(request: Request):
    # Terima POST body pun tetep balikin JSON yang sama
    body = {}
    try:
        body = await request.json()
    except:
        pass
    print(f"OTA check dari robot: {body}")
    
    return {
        "firmware": {
            "version": "2.4.2-amix-kuningan",
            "url": ""
        },
        "websocket": {
            "url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/",
            "token": ""
        },
        "server_time": {
            "timestamp": 0,
            "timezone_offset": 420
        }
    }

@app.websocket("/xiaozhi/v1/")
async def xiaozhi_ws(websocket: WebSocket):
    await websocket.accept()
    print("Robot Kuningan konek!")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Kalau robot ngirim hello
            if msg.get("type") == "hello":
                await websocket.send_text(json.dumps({
                    "type": "hello",
                    "transport": "websocket",
                    "audio_params": {"sample_rate": 16000}
                }))
            # Kalau robot ngirim STT text
            if "text" in str(data):
                # Balas pakai Sunda Kuningan!
                await websocket.send_text(json.dumps({
                    "type": "tts",
                    "state": "sentence_start",
                    "text": "Halo bos! Abdi Siaga ti Kuningan, kumaha?"
                }))
    except:
        print("Robot disconnect")

@app.get("/")
def root():
    return {"status": "AMIX Kuningan Cloud Siaga"}
