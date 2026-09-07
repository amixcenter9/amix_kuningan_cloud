import os, json, logging, tempfile, shutil, subprocess, asyncio, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v10-hello")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
logger.info(f"KEY LEN: {len(GEMINI_API_KEY)}")
MODEL_NAME = "gemini-2.0-flash"
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY MODEL: {MODEL_NAME}")

try:
    import yt_dlp
    YTDLP_OK=True
    logger.info("yt-dlp READY")
except:
    YTDLP_OK=False

FFMPEG_OK = shutil.which("ffmpeg") is not None
logger.info(f"ffmpeg: {FFMPEG_OK}")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Amix V10 HELLO FIX READY"}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    # PENTING: kasih websocket url yang benar
    return {
        "firmware": {"version": "2.4.2-amix-v10"},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/", "token": "test"}
    }

@app.websocket("/xiaozhi/v1/")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS CONNECTED - sending HELLO")
    
    # 1. KIRIM HELLO DULU - INI YANG BIKIN GAK MENGHUBUNGKAN TERUS!
    hello = {
        "type": "hello",
        "version": 1,
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16000,
            "channels": 1,
            "frame_duration": 60
        }
    }
    await websocket.send_text(json.dumps(hello))
    logger.info("HELLO SENT")

    # 2. LOOP
    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("WS DISCONNECTED by client")
                break

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except:
                    logger.info(f"RAW TEXT: {message['text'][:100]}")
                    continue

                msg_type = data.get("type","")
                # logger.info(f"RECV type={msg_type}")

                if msg_type == "hello":
                    # client hello, balas lagi hello biar yakin
                    await websocket.send_text(json.dumps(hello))
                    logger.info("CLIENT HELLO - REPLY HELLO")

                elif msg_type == "listen":
                    state = data.get("state")
                    text = data.get("text","")
                    logger.info(f"LISTEN {state} txt='{text}'")
                    if state == "start":
                        # kirim stt biar OLED gak mendengarkan terus
                        await websocket.send_text(json.dumps({"type": "stt", "text": "Siap bos"}))

                elif msg_type == "text" or "text" in data:
                    user_text = data.get("text") or data.get("data") or ""
                    if isinstance(user_text, dict):
                        user_text = user_text.get("text","")
                    user_text = str(user_text).strip()
                    if len(user_text) < 2:
                        continue
                    logger.info(f"USER TEXT: {user_text}")

                    # Musik?
                    is_music = any(k in user_text.lower() for k in ["putar","lagu","musik","play","komang","bernadya","juicy","tenxi","dj"])
                    if is_music and YTDLP_OK and FFMPEG_OK:
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start", "text": f"Muter {user_text} ya bos"}))
                        # Untuk test, skip download dulu, kirim TTS dulu biar gak 1005
                        # (download youtube butuh waktu lama bisa timeout)
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"Siap bos, lagi nyari lagu {user_text}, bentar ya"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                        continue

                    # Gemini chat
                    try:
                        model = genai.GenerativeModel(MODEL_NAME)
                        prompt = f"Kamu Siaga asisten Amix Kuningan, jawab singkat max 1 kalimat, santai: {user_text}"
                        resp = await asyncio.to_thread(model.generate_content, prompt)
                        ai_text = resp.text.strip()
                        logger.info(f"GEMINI OK: {ai_text[:80]}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                    except Exception as e:
                        logger.error(f"GEMINI ERR {e}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Halo bos! Siaga udah online nih!"}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))

                elif msg_type == "abort":
                    logger.info("ABORT received")
                    await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))

            if "bytes" in message:
                # audio binary dari ESP32 - jangan di-log kebanyakan
                # logger.info(f"AUDIO {len(message['bytes'])} bytes")
                pass

    except Exception as e:
        logger.error(f"WS ERR {e}")
    finally:
        logger.info("WS DISCONNECTED")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8080")))
