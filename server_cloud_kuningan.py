from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, logging, os, asyncio
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("siaga-FINAL-FIX")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip()
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY {MODEL_NAME} LEN {len(GEMINI_API_KEY)}")

app = FastAPI()

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
@app.get("/xiaozhi/ota")
@app.post("/xiaozhi/ota")
async def ota(request: Request):
    logger.info("OTA HIT!")
    return JSONResponse({
        "firmware": {"version": "2.4.2-amix-final", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/")
def root():
    return {"status":"Siaga Online Final Fix","model":MODEL_NAME}

@app.websocket("/xiaozhi/v1/")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS CONNECTED - sending HELLO")
    await websocket.send_text(json.dumps({
        "type": "hello",
        "transport": "websocket",
        "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1}
    }))
    logger.info("HELLO SENT")

    while True:
        try:
            data = await websocket.receive_text()
            msg = json.loads(data)
            logger.info(f"RECV: {msg}")

            # Client hello
            if msg.get("type") == "hello":
                logger.info(f"CLIENT HELLO {msg.get('session_id')}")
                continue

            # Listen
            if msg.get("type") == "listen":
                txt = msg.get("text","")
                state = msg.get("state","")
                logger.info(f"LISTEN state={state} txt='{txt}'")
                if txt and len(txt.strip()) > 0:
                    user_text = txt.strip()
                    ai_text = f"Kumaha bos! Abdi ngadangu: {user_text}"
                    if GEMINI_API_KEY:
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            resp = await asyncio.to_thread(model.generate_content, f"Kamu Siaga Sunda Kuningan jawab singkat 20 kata: {user_text}")
                            ai_text = resp.text.strip()[:150]
                            logger.info(f"GEMINI OK: {ai_text}")
                        except Exception as e:
                            logger.error(f"GEMINI ERR {e}")
                    logger.info(f"SEND TTS: {ai_text}")
                    await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": ai_text}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                    logger.info("TTS SENT DONE")
        except Exception as e:
            logger.error(f"WS ERR {e}")
            break
    logger.info("WS DISCONNECTED")
