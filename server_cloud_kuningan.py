from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, logging, os, asyncio
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("siaga-V13-FIX")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY {MODEL_NAME}")

app = FastAPI()

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
@app.get("/xiaozhi/ota")
@app.post("/xiaozhi/ota")
async def ota(request: Request):
    return JSONResponse({
        "firmware": {"version": "2.4.2-V13", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/")
def root(): 
    return {"status": "Siaga V13 Anti Error Text"}

@app.websocket("/xiaozhi/v1/")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS CONNECTED - HELLO SENT")
    
    # Kirim Hello awal
    await websocket.send_text(json.dumps({
        "type": "hello",
        "transport": "websocket",
        "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1}
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            state = msg.get("state", "")
            text = msg.get("text", "")

            # Log singkat aktivitas selain stream audio mentah
            if msg_type != "listen" or state != "start":
                logger.info(f"RECV type={msg_type} state={state} txt={text[:30]}")

            # Tangani pesan dari client (ESP32)
            if msg_type == "listen":
                if state == "start":
                    logger.info("LISTEN START - perangkat mulai mendengar...")
                    continue  

                if state == "stop" and text:
                    user_text = text.strip()
                    logger.info(f"USER NGOMONG: {user_text}")

                    # Panggil Gemini API
                    ai_text = f"Kumaha bos! Siaga ngadangu: {user_text}"
                    if GEMINI_API_KEY and user_text:
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            prompt = f"Kamu Siaga asisten Sunda Kuningan, jawab santai singkat max 25 kata. User: {user_text}"
                            resp = await asyncio.to_thread(model.generate_content, prompt)
                            if resp and resp.text:
                                ai_text = resp.text.strip()[:180]
                            logger.info(f"GEMINI: {ai_text}")
                        except Exception as e:
                            logger.error(f"GEMINI ERR {e}")

                    # --- KRUSIAL: KONTROL STATE AGAR TIDAK LOOPING ---
                    # 1. Beritahu perangkat bahwa server mulai mengirim audio/TTS
                    await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                    
                    # 2. Kirim teks kalimat (bisa dipecah atau langsung)
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text}))
                    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": ai_text}))
                    
                    # 3. Tutup sesi TTS agar perangkat tahu AI selesai bicara
                    await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                    logger.info(f"TTS SENT: {ai_text}")

                    # 4. Beritahu perangkat untuk kembali mendengarkan (opsional tapi disarankan tergantung firmware)
                    # atau biarkan perangkat state ke idle/listen secara otomatis setelah tts stop.

            # Tangani jika client mengirim abort/cancel
            elif msg_type == "abort":
                logger.info("CLIENT ABORTED SESI")
                
    except Exception as e:
        logger.error(f"WS ERR {e}")
    finally:
        logger.info("WS DISCONNECTED")
