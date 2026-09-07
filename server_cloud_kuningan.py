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
    
    # 1. Kirim Hello awal ke ESP32
    try:
        await websocket.send_text(json.dumps({
            "type": "hello",
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1}
        }))
    except Exception as e:
        logger.error(f"Gagal kirim hello: {e}")
        return

    try:
        while True:
            raw = await websocket.receive_text()
            
            # Parsing JSON yang aman
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Bukan JSON valid: {raw[:50]}")
                continue

            # Ambil parameter dengan aman tanpa takut KeyError
            msg_type = msg.get("type", "unknown")
            state = msg.get("state", "")
            text = msg.get("text", "")

            logger.info(f"RECV -> type: {msg_type} | state: {state} | text_len: {len(text)}")

            # 2. Tangani berdasarkan tipe pesan
            if msg_type == "hello":
                logger.info("ESP32 HELLO RECEIVED - Perangkat siap.")
                continue

            elif msg_type == "listen":
                if state == "start":
                    logger.info("LISTEN START - Perangkat mulai mendengar user...")
                    continue  

                elif state == "stop":
                    user_text = text.strip() if text else ""
                    logger.info(f"USER NGOMONG (TEXT): '{user_text}'")

                    # Default balasan jika teks kosong atau gemini mati
                    ai_text = "Maaf bos, suara tidak terdengar jelas."
                    
                    if user_text and GEMINI_API_KEY:
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            prompt = f"Kamu Siaga asisten Sunda Kuningan, jawab santai singkat max 25 kata. User: {user_text}"
                            resp = await asyncio.to_thread(model.generate_content, prompt)
                            if resp and resp.text:
                                ai_text = resp.text.strip()[:180]
                            logger.info(f"GEMINI RESPONSE: {ai_text}")
                        except Exception as e:
                            logger.error(f"GEMINI ERR: {e}")
                            ai_text = "Haduh bos, otak saya lagi konslet nih."

                    # Kirim respon TTS ke ESP32 secara berurutan & aman
                    try:
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": ai_text}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                        logger.info(f"TTS SENT SUCCESSFULLY: {ai_text}")
                    except Exception as e:
                        logger.error(f"GAGAL KIRIM TTS: {e}")

            elif msg_type == "abort":
                logger.info("KLIEN MENGIRIM ABORT SESI")
                
    except Exception as e:
        logger.error(f"WS CRITICAL ERR: {str(e)}")
    finally:
        logger.info("WS DISCONNECTED")
