import os, json, logging, asyncio, tempfile, shutil, subprocess, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v11-final")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().replace("\n","").replace(" ","")
logger.info(f"KEY LEN: {len(GEMINI_API_KEY)}")
MODEL_NAME = "gemini-2.0-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"GEMINI READY MODEL: {MODEL_NAME}")
try:
    import yt_dlp
    YTDLP_OK=True
    logger.info("yt-dlp READY - YOUTUBE DJ READY!")
except:
    YTDLP_OK=False
FFMPEG_OK = shutil.which("ffmpeg") is not None
logger.info(f"ffmpeg: {FFMPEG_OK}")

app = FastAPI()

@app.get("/")
async def root():
    return {"status":"Amix V11 FINAL FIX LISTENING","model":MODEL_NAME,"key_len":len(GEMINI_API_KEY),"ffmpeg":FFMPEG_OK,"ytdlp":YTDLP_OK}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota():
    return {
        "firmware": {"version": "2.4.2-amix-v11","url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"}
    }

@app.websocket("/xiaozhi/v1/")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("amix-v11-final:WS CONNECTED - sending HELLO")
    # Kirim HELLO sesuai protokol Xiaozhi
    hello = {
        "type": "hello",
        "version": 2,
        "transport": "websocket",
        "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}
    }
    await websocket.send_text(json.dumps(hello))
    logger.info("amix-v11-final:HELLO SENT")

    audio_buffer = []
    session_id = ""

    try:
        while True:
            # Terima TEXT atau BINARY
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except:
                    continue
                
                # HELLO dari client
                if data.get("type") == "hello":
                    session_id = data.get("session_id","")
                    logger.info(f"amix-v11-final:CLIENT HELLO - REPLY HELLO session={session_id}")
                    # sudah kirim hello di atas, tidak perlu lagi
                    continue
                
                # LISTEN start
                if data.get("type") == "listen":
                    state = data.get("state")
                    txt = data.get("text","")
                    logger.info(f"amix-v11-final:LISTEN {state} txt='{txt}' session={session_id}")
                    if state == "start":
                        audio_buffer = []
                    if state == "stop" or (txt and len(txt)>1):
                        # Jika device sudah STT sendiri dan kirim text
                        user_text = txt
                        if user_text:
                            logger.info(f"USER TEXT: {user_text}")
                            await handle_chat(websocket, user_text)
                    continue

                if data.get("type") == "text":
                    user_text = data.get("text","").strip()
                    if user_text:
                        logger.info(f"USER TEXT: {user_text}")
                        await handle_chat(websocket, user_text)
                    continue

                # ABORT
                if data.get("type") == "abort":
                    audio_buffer = []
                    continue

            elif "bytes" in message:
                # Audio binary OPUS dari ESP32
                audio_buffer.append(message["bytes"])
                # logger.info(f"AUDIO CHUNK {len(message['bytes'])} total {len(audio_buffer)}")
                continue

    except WebSocketDisconnect:
        logger.info("amix-v11-final:WS DISCONNECTED (client disconnect)")
    except Exception as e:
        logger.error(f"amix-v11-final:WS ERR {e}")
        try:
            await websocket.close()
        except:
            pass

async def handle_chat(websocket: WebSocket, user_text: str):
    lower = user_text.lower()
    is_music = any(k in lower for k in ["putar","play","lagu","musik","komang","bernadya","juicy","tenxi","dj","koplo","dangdut","musik"])
    
    if is_music and YTDLP_OK and FFMPEG_OK:
        await websocket.send_text(json.dumps({"type":"tts","state":"start","text":f"Siap bos, muter {user_text}!"}))
        try:
            # search & download handled in thread
            def search_dl():
                ydl_opts_search = {'format':'bestaudio/best','quiet':True,'noplaylist':True,'default_search':'ytsearch1'}
                with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{user_text} lagu", download=False)
                    entry = info['entries'][0] if 'entries' in info else info
                    url = entry.get('webpage_url') or entry.get('url')
                    if not url:
                        return None, None
                    tmpdir = tempfile.mkdtemp()
                    outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")
                    ydl_opts = {'format':'bestaudio/best','outtmpl':outtmpl,'quiet':True,'noplaylist':True}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                        ydl2.extract_info(url, download=True)
                    files = os.listdir(tmpdir)
                    audio_file = None
                    for f in files:
                        if f.endswith((".webm",".m4a",".mp3",".opus",".mp4",".ogg")):
                            audio_file = os.path.join(tmpdir, f)
                            break
                    return audio_file, tmpdir
            audio_file, tmpdir = await asyncio.to_thread(search_dl)
            if audio_file and os.path.exists(audio_file):
                opus_path = os.path.join(tmpdir, "out.opus")
                subprocess.run(["ffmpeg","-y","-i",audio_file,"-ar","16000","-ac","1","-c:a","libopus","-b:a","32k",opus_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(opus_path):
                    with open(opus_path,"rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":f"Memutar {user_text}"}))
                    await websocket.send_text(json.dumps({"type":"audio","audio":b64,"format":"opus","sample_rate":16000}))
                    logger.info(f"YT PLAYED: {user_text}")
                shutil.rmtree(tmpdir, ignore_errors=True)
                await websocket.send_text(json.dumps({"type":"tts","state":"stop"}))
                return
        except Exception as e:
            logger.error(f"YT ERR {e}")
        await websocket.send_text(json.dumps({"type":"tts","state":"start","text":"Lagu tidak ketemu bos"}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop"}))
        return

    # GEMINI CHAT
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"Kamu Siaga, asisten Amix Kuningan. Jawab singkat max 2 kalimat, santai Sunda. User: {user_text}"
        resp = await asyncio.to_thread(model.generate_content, prompt)
        ai_text = resp.text.strip()
        logger.info(f"GEMINI OK: {ai_text[:100]}")
        await websocket.send_text(json.dumps({"type":"tts","state":"start"}))
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":ai_text}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop"}))
    except Exception as e:
        logger.error(f"GEMINI ERR {e}")
        await websocket.send_text(json.dumps({"type":"tts","state":"start","text":"Halo bos, Siaga sudah online di V11!"}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop"}))
