
import os
from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {
        "status": "AMIX AI KUNINGAN - CLOUD AKTIF 24 JAM",
        "ws_url": "wss://HOST_KAMU/xiaozhi/v1/",
        "tim": "Kuningan Jabar"
    }

@app.websocket("/xiaozhi/v1/")
async def xiaozhi_ws(websocket: WebSocket):
    await websocket.accept()
    print("=== ESP32 KUNINGAN KONEK DARI CLOUD ===")
    await websocket.send_json({"type":"hello","version":3,"audio_params":{"format":"opus","sample_rate":16000,"channels":1}})
    while True:
        try:
            data = await websocket.receive()
            if "bytes" in data:
                jawaban = "Halo Bos Kuningan! Ini AMIX AI Cloud 24 jam aktif tanpa HP dan tanpa komputer. Mantap Tim Teknologi Kuningan!"
                await websocket.send_json({"type":"tts","state":"start","text": jawaban})
                await websocket.send_json({"type":"tts","state":"sentence_start","text": jawaban})
                await websocket.send_json({"type":"tts","state":"sentence_end","text": jawaban})
                await websocket.send_json({"type":"tts","state":"stop"})
            else:
                txt = data.get("text","")
                if txt: print("ESP:", str(txt)[:200])
        except Exception as e:
            print("Disconnect:", e)
            break

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
