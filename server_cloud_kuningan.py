import os, json, logging, tempfile, shutil, subprocess, asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v9-fastapi")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().replace("\n","").replace(" ","").replace("\r","")
logger.info(f"KEY LEN: {len(GEMINI_API_KEY)}")

MODEL_NAME = "gemini-2.0-flash"  # FIX 2026 - gemini-1.5-flash mati di v1beta

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"GEMINI READY MODEL: {MODEL_NAME}")
    except Exception as e:
        logger.error(f"GEMINI CONFIG ERR: {e}")
else:
    logger.error("GEMINI KEY MISSING!")

try:
    import yt_dlp
    YTDLP_OK = True
    logger.info("yt-dlp READY - YOUTUBE DJ READY!")
except:
    YTDLP_OK = False

FFMPEG_OK = shutil.which("ffmpeg") is not None
logger.info(f"ffmpeg: {FFMPEG_OK}")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Amix Kuningan Cloud V9 FASTAPI READY", "model": MODEL_NAME, "key_len": len(GEMINI_API_KEY), "ffmpeg": FFMPEG_OK, "ytdlp": YTDLP_OK}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    return {
        "firmware": {"version": "2.4.2-amix-v9-fastapi", "url": ""},
        "websocket": {"url": f"wss://{os.getenv('RAILWAY_PUBLIC_DOMAIN','amixkuningancloud-production.up.railway.app')}/xiaozhi/v1/".replace("https://","wss://").replace("http://","ws://") if os.getenv('RAILWAY_PUBLIC_DOMAIN') else "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"}
    }

def search_youtube(query: str):
    if not YTDLP_OK:
        return None
    try:
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True, 'default_search': 'ytsearch1', 'extract_flat': False}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in info and info['entries']:
                return info['entries'][0]
            return info
    except Exception as e:
        logger.error(f"YT SEARCH ERR: {e}")
        return None

@app.websocket("/xiaozhi/v1/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS CONNECTED")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except:
                msg = {"text": data}

            # Log
            if msg.get("type") == "listen":
                logger.info(f"LISTEN start txt='{msg.get('text','')}'")
                continue
            if msg.get("type") == "audio":
                continue

            user_text = msg.get("text") or msg.get("data") or ""
            if isinstance(user_text, dict):
                user_text = user_text.get("text","")
            user_text = str(user_text).strip()
            if not user_text or len(user_text) < 2:
                # kadang text kosong karena masih listening
                continue

            logger.info(f"USER TEXT: {user_text}")

            # Cek musik?
            lower = user_text.lower()
            is_music = any(k in lower for k in ["putar", "play", "lagu", "musik", "komang", "bernadya", "juicy luicy", "tenxi", "dj", "koplo", "dangdut"])

            if is_music and YTDLP_OK and FFMPEG_OK:
                await websocket.send_text(json.dumps({"type": "tts", "state": "start", "text": f"Siap bos, muter {user_text}!"}))
                try:
                    entry = await asyncio.to_thread(search_youtube, user_text)
                    if entry:
                        url = entry.get('webpage_url') or entry.get('url')
                        if url:
                            tmpdir = tempfile.mkdtemp()
                            outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")
                            ydl_opts = {
                                'format': 'bestaudio/best',
                                'outtmpl': outtmpl,
                                'quiet': True,
                                'noplaylist': True,
                            }
                            def dl():
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                    info = ydl.extract_info(url, download=True)
                                    return info
                            info = await asyncio.to_thread(dl)
                            # cari file audio
                            files = os.listdir(tmpdir)
                            audio_file = None
                            for f in files:
                                if f.endswith((".webm",".m4a",".mp3",".opus",".mp4")):
                                    audio_file = os.path.join(tmpdir, f)
                                    break
                            if audio_file:
                                opus_path = os.path.join(tmpdir, "out.opus")
                                subprocess.run(["ffmpeg","-y","-i",audio_file,"-ar","16000","-ac","1","-c:a","libopus","-b:a","32k",opus_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                if os.path.exists(opus_path):
                                    import base64
                                    with open(opus_path,"rb") as af:
                                        b64 = base64.b64encode(af.read()).decode()
                                    # kirim sesuai protokol xiaozhi: audio binary base64
                                    await websocket.send_text(json.dumps({"type": "audio", "audio": b64, "format": "opus", "sample_rate": 16000}))
                                    logger.info(f"YT PLAYED: {user_text}")
                            shutil.rmtree(tmpdir, ignore_errors=True)
                            await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                            continue
                except Exception as e:
                    logger.error(f"YT PLAY ERR: {e}")

                await websocket.send_text(json.dumps({"type": "tts", "state": "start", "text": "Lagu tidak ketemu bos, coba judul lain"}))
                await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
                continue

            # AI CHAT
            try:
                model = genai.GenerativeModel(MODEL_NAME)
                prompt = f"Kamu adalah Siaga, asisten AI dari Amix Kuningan, Jawa Barat. Jawab singkat, santai, bahasa Indonesia campur Sunda, maksimal 2 kalimat. User bilang: {user_text}"
                resp = await asyncio.to_thread(model.generate_content, prompt)
                ai_text = resp.text.strip()
                logger.info(f"GEMINI OK: {ai_text[:100]}")
                await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
                await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text}))
                await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))
            except Exception as e:
                logger.error(f"GEMINI ERR {e}")
                # Kirim fallback biar gak looping mendengarkan terus
                await websocket.send_text(json.dumps({"type": "tts", "state": "start", "text": "Halo bos, Siaga sudah online! Silakan ngobrol!"}))
                await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))

    except Exception as e:
        logger.error(f"WS ERR {e}")
    finally:
        logger.info("WS DISCONNECTED")

# Untuk uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8080")))
