import os, json, logging, tempfile, shutil, subprocess, asyncio, base64
from fastapi import FastAPI, WebSocket
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v10-final")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().replace("\n","").replace(" ","").replace("\r","")
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY MODEL: {MODEL_NAME} KEY LEN: {len(GEMINI_API_KEY)}")
else:
    logger.error("KEY MISSING!")

try:
    import yt_dlp
    YTDLP_OK = True
    logger.info("yt-dlp READY!")
except:
    YTDLP_OK = False

FFMPEG_OK = shutil.which("ffmpeg") is not None
logger.info(f"ffmpeg: {FFMPEG_OK}")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Amix V10 FINAL HELLO+STT", "model": MODEL_NAME}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "amixkuningancloud-production.up.railway.app")
    ws_url = f"wss://{domain}/xiaozhi/v1/"
    return {
        "firmware": {"version": "2.4.2-amix-v10", "url": ""},
        "websocket": {"url": ws_url}
    }

@app.websocket("/xiaozhi/v1/")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS CONNECTED - sending HELLO")
    # HELLO PROTOCOL WAJIB XIAOZHI
    hello = {
        "type": "hello",
        "version": 3,
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 24000,
            "channels": 1,
            "frame_duration": 60
        }
    }
    await websocket.send_text(json.dumps(hello))
    logger.info("HELLO SENT")

    audio_buffer = bytearray()
    session_id = ""

    try:
        while True:
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except:
                    continue

                msg_type = data.get("type","")

                if msg_type == "hello":
                    session_id = data.get("session_id","")
                    logger.info(f"CLIENT HELLO - REPLY HELLO session={session_id[:8]}")
                    # reply hello again untuk pastikan
                    await websocket.send_text(json.dumps(hello))
                    continue

                if msg_type == "listen":
                    state = data.get("state","")
                    txt = data.get("text","")
                    logger.info(f"LISTEN {state} txt='{txt}' session={session_id[:8] if session_id else ''}")
                    if state == "start":
                        audio_buffer = bytearray()
                        # kasih tau device kita dengerin
                        await websocket.send_text(json.dumps({"type": "stt", "text": "mendengarkan...", "session_id": session_id}))
                    elif state == "stop":
                        # STT PROCESS
                        if len(audio_buffer) > 0:
                            logger.info(f"AUDIO BUFFER {len(audio_buffer)} bytes -> STT")
                            # save opus to wav
                            tmpdir = tempfile.mkdtemp()
                            opus_path = os.path.join(tmpdir, "input.opus")
                            wav_path = os.path.join(tmpdir, "input.wav")
                            with open(opus_path,"wb") as f:
                                f.write(audio_buffer)
                            # convert opus 16k -> wav 16k
                            subprocess.run(["ffmpeg","-y","-i",opus_path,"-ar","16000","-ac","1",wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            # transcribe pakai gemini audio
                            try:
                                if os.path.exists(wav_path):
                                    with open(wav_path,"rb") as wf:
                                        wav_data = wf.read()
                                    model = genai.GenerativeModel(MODEL_NAME)
                                    # gemini bisa terima audio via inline_data
                                    response = await asyncio.to_thread(
                                        model.generate_content,
                                        [
                                            {"mime_type": "audio/wav", "data": base64.b64encode(wav_data).decode()},
                                            "Transkrip audio ini ke teks Indonesia singkat saja, kalau tidak jelas tulis 'halo'"
                                        ]
                                    )
                                    user_text = response.text.strip()
                                    logger.info(f"STT RESULT: {user_text}")
                                    await websocket.send_text(json.dumps({"type": "stt", "text": user_text, "session_id": session_id}))
                                    audio_buffer = bytearray()
                                    # lanjut ke AI
                                    data = {"type": "text", "text": user_text}
                                else:
                                    audio_buffer = bytearray()
                                    continue
                            except Exception as e:
                                logger.error(f"STT ERR {e}")
                                audio_buffer = bytearray()
                                # fallback
                                user_text = txt if txt else "halo"
                                data = {"type": "text", "text": user_text}
                            shutil.rmtree(tmpdir, ignore_errors=True)
                        else:
                            if txt:
                                data = {"type": "text", "text": txt}
                            else:
                                continue
                    else:
                        continue

                # TEXT HANDLER (setelah STT atau langsung dari device)
                if data.get("type") == "text" or "text" in data:
                    user_text = data.get("text","") or data.get("data","")
                    if isinstance(user_text, dict):
                        user_text = user_text.get("text","")
                    user_text = str(user_text).strip()
                    if not user_text or len(user_text) < 1:
                        continue
                    
                    logger.info(f"USER TEXT FINAL: {user_text}")

                    # MUSIC?
                    lower = user_text.lower()
                    is_music = any(k in lower for k in ["putar","play","lagu","musik","komang","bernadya","juicy","tenxi","dj","koplo","dangdut","hivi","malam"])

                    if is_music and YTDLP_OK and FFMPEG_OK:
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"Siap bos, muter lagu {user_text}!", "session_id": session_id}))
                        # search & play - simplified for stability
                        try:
                            def search_and_dl(q):
                                ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True, 'default_search': 'ytsearch1'}
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                    info = ydl.extract_info(f"ytsearch1:{q}", download=False)
                                    if 'entries' in info:
                                        entry = info['entries'][0]
                                    else:
                                        entry = info
                                    url = entry.get('webpage_url')
                                    # download
                                    tmp = tempfile.mkdtemp()
                                    outtmpl = os.path.join(tmp, "%(title)s.%(ext)s")
                                    ydl_opts2 = {'format': 'bestaudio/best', 'outtmpl': outtmpl, 'quiet': True, 'noplaylist': True}
                                    with yt_dlp.YoutubeDL(ydl_opts2) as ydl2:
                                        ydl2.extract_info(url, download=True)
                                    # find file
                                    for f in os.listdir(tmp):
                                        fp = os.path.join(tmp, f)
                                        if os.path.isfile(fp):
                                            return fp, tmp, entry.get('title','')
                                    return None, tmp, ""
                            audio_file, tmpdir, title = await asyncio.to_thread(search_and_dl, user_text)
                            if audio_file and os.path.exists(audio_file):
                                opus_out = os.path.join(tmpdir, "out.opus")
                                subprocess.run(["ffmpeg","-y","-i",audio_file,"-ar","24000","-ac","1","-c:a","libopus","-b:a","48k",opus_out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                if os.path.exists(opus_out):
                                    with open(opus_out,"rb") as af:
                                        b64 = base64.b64encode(af.read()).decode()
                                    await websocket.send_text(json.dumps({"type": "audio", "audio": b64, "format": "opus", "sample_rate": 24000, "session_id": session_id}))
                                    logger.info(f"YT PLAYED {title}")
                                shutil.rmtree(tmpdir, ignore_errors=True)
                            await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                            continue
                        except Exception as e:
                            logger.error(f"YT ERR {e}")
                            await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                            continue

                    # GEMINI CHAT
                    try:
                        model = genai.GenerativeModel(MODEL_NAME)
                        prompt = f"Kamu Siaga, asisten Amix Kuningan. Jawab santai Sunda, max 2 kalimat pendek. User: {user_text}"
                        resp = await asyncio.to_thread(model.generate_content, prompt)
                        ai_text = resp.text.strip()
                        logger.info(f"GEMINI OK: {ai_text}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": ai_text, "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))
                    except Exception as e:
                        logger.error(f"GEMINI ERR {e}")
                        await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Halo bos! Siaga udah online nih!", "session_id": session_id}))
                        await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))

            if "bytes" in message:
                # audio binary opus dari ESP32
                audio_buffer.extend(message["bytes"])
                # logger.info(f"AUDIO CHUNK {len(message['bytes'])} total {len(audio_buffer)}")

    except Exception as e:
        logger.error(f"WS ERR {e}")
    finally:
        logger.info("WS DISCONNECTED")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8080")))
