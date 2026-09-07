from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
import json, logging, os, asyncio
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("siaga-final")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip()
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY {MODEL_NAME}")

app = FastAPI()

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    return JSONResponse({
        "firmware": {"version": "2.4.2-amix", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"}
    })

@app.get("/")
def root(): return {"status":"Siaga Online"}

@app.websocket("/xiaozhi/v1/")
async def ws(ws: WebSocket):
    await ws.accept()
    await ws.send_text(json.dumps({"type":"hello","transport":"websocket","audio_params":{"format":"opus","sample_rate":16000,"channels":1}}))
    while True:
        try:
            data = await ws.receive_text()
            m = json.loads(data)
            if m.get("type") == "listen" and m.get("text"):
                txt = m.get("text")
                logger.info(f"USER: {txt}")
                ai = f"Kumaha bos! Abdi Siaga ngadangu: {txt}"
                if GEMINI_API_KEY:
                    try:
                        model = genai.GenerativeModel(MODEL_NAME)
                        r = await asyncio.to_thread(model.generate_content, f"Jawab singkat Sunda 20 kata: {txt}")
                        ai = r.text.strip()[:150]
                    except: pass
                await ws.send_text(json.dumps({"type":"tts","state":"start"}))
                await ws.send_text(json.dumps({"type":"tts","state":"sentence_start","text":ai}))
                await ws.send_text(json.dumps({"type":"tts","state":"sentence_end","text":ai}))
                await ws.send_text(json.dumps({"type":"tts","state":"stop"}))
        except: break
