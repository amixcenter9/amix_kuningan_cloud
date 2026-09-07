import os, json, logging, asyncio, tempfile, shutil, subprocess, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v10-final")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
logger.info(f"KEY LEN: {len(GEMINI_API_KEY)}")
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY MODEL: {MODEL_NAME}")
else:
    logger.error("NO KEY!")

try:
    import yt_dlp
    YTDLP = True
    logger.info("yt-dlp READY")
except:
    YTDLP = False

FFMPEG = shutil.which("ffmpeg") is not None
logger.info(f"FFMPEG: {FFMPEG}")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "AMIX V10 FINAL XIAOZHI PROTOCOL OK", "model": MODEL_NAME, "key_len": len(GEMINI_API_KEY)}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    return {
        "firmware": {"version": "2.4.2-amix-v10", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"}
    }

def search_yt(q):
    try:
        opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True, 'default_search': 'ytsearch1'}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{q}", download=False)
            if info.get('entries'):
                return info['entries'][0]
            return info
    except Exception as e:
        logger.error(f"YT ERR {e}")
        return None

@app.websocket("/xiaozhi/v1/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WS CONNECTED - sending HELLO")
    session_id = os.urandom(8).hex()
    
    # HELLO SERVER - INI YANG BIKIN SIAGA GAK MENDENGARKAN TERUS!
    hello_server = {
        "type": "hello",
        "version": 1,
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16000,
            "channels": 1,
            "frame_duration": 60
        },
        "session_id": session_id
    }
    await ws.send_text(json.dumps(hello_server))
    logger.info("HELLO SENT")

    try:
        while True:
            # PENTING: pakai receive() bukan receive_text() biar gak crash kalau device kirim binary!
            message = await ws.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except:
                    continue

                mtype = data.get("type","")
                # logger.info(f"RECV {mtype} {str(data)[:200]}")

                if mtype == "hello":
                    logger.info(f"CLIENT HELLO - REPLY HELLO session={data.get('session_id','')}")
                    # sudah reply di atas, jangan reply lagi
                    continue

                if mtype == "listen":
                    state = data.get("state","")
                    txt = data.get("text","")
                    logger.info(f"LISTEN {state} txt='{txt}' session={session_id}")
                    
                    if state == "start":
                        # Device mulai mendengarkan
                        await ws.send_text(json.dumps({"type": "stt", "text": "mendengarkan...", "session_id": session_id}))
                    
                    if state == "stop" or (state == "detect" and txt):
                        user_text = txt or data.get("data","") or ""
                        if not user_text:
                            user_text = data.get("text","")
                        user_text = str(user_text).strip()
                        
                        if len(user_text) < 2:
                            # Kalau text kosong, kirim fallback biar gak loop
                            await ws.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Halo bos, Siaga dengar, silakan ngomong lagi!", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                            continue

                        logger.info(f"USER TEXT FINAL: {user_text}")

                        # CEK MUSIK
                        is_music = any(k in user_text.lower() for k in ["putar", "lagu", "musik", "play", "komang", "bernadya", "juicy", "dj", "koplo"])
                        if is_music and YTDLP and FFMPEG:
                            await ws.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"Siap bos, putar {user_text}", "session_id": session_id}))
                            entry = await asyncio.to_thread(search_yt, user_text)
                            if entry:
                                url = entry.get("webpage_url") or entry.get("url")
                                if url:
                                    tmpdir = tempfile.mkdtemp()
                                    outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")
                                    def dl():
                                        opts = {'format': 'bestaudio/best', 'outtmpl': outtmpl, 'quiet': True, 'noplaylist': True}
                                        with yt_dlp.YoutubeDL(opts) as ydl:
                                            ydl.extract_info(url, download=True)
                                    await asyncio.to_thread(dl)
                                    audio_file = None
                                    for f in os.listdir(tmpdir):
                                        if f.endswith((".webm",".m4a",".mp3",".mp4",".opus")):
                                            audio_file = os.path.join(tmpdir, f)
                                            break
                                    if audio_file:
                                        opus_out = os.path.join(tmpdir, "out.opus")
                                        subprocess.run(["ffmpeg","-y","-i",audio_file,"-ar","16000","-ac","1","-c:a","libopus","-b:a","32k",opus_out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        if os.path.exists(opus_out):
                                            with open(opus_out,"rb") as af:
                                                b64 = base64.b64encode(af.read()).decode()
                                            # Kirim audio pakai format xiaozhi v1
                                            await ws.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                                            await ws.send_text(json.dumps({"type": "audio", "audio": b64, "format": "opus", "sample_rate": 16000, "session_id": session_id}))
                                            await ws.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                                            logger.info(f"YT PLAYED {user_text}")
                                            shutil.rmtree(tmpdir, ignore_errors=True)
                                            continue
                                    shutil.rmtree(tmpdir, ignore_errors=True)
                            await ws.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                            continue

                        # AI GEMINI
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            prompt = f"Kamu Siaga, asisten Amix Kuningan, jawab singkat santai 1-2 kalimat bahasa Indonesia campur Sunda. User: {user_text}"
                            resp = await asyncio.to_thread(model.generate_content, prompt)
                            ai_text = resp.text.strip()
                            logger.info(f"GEMINI OK: {ai_text}")
                            await ws.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text, "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                        except Exception as e:
                            logger.error(f"GEMINI ERR {e}")
                            await ws.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Halo bos, Siaga online! Coba ngomong lagi ya!", "session_id": session_id}))
                            await ws.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))

                if mtype == "abort":
                    logger.info("ABORT")
                    continue

            if "bytes" in message:
                # Audio opus dari device, abaikan untuk sekarang (device sudah STT sendiri)
                # logger.info(f"AUDIO BYTES {len(message['bytes'])}")
                continue

    except WebSocketDisconnect:
        logger.info("WS DISCONNECTED")
    except Exception as e:
        logger.error(f"WS ERR {e}")
