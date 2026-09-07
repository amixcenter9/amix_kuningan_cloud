import os, asyncio, json, base64, logging, time, re, subprocess, tempfile, shutil
from aiohttp import web
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amix-v9")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().replace("\n","").replace(" ","")
logger.info(f"KEY LEN: {len(GEMINI_API_KEY)}")
logger.info(f"KEY PREFIX: {GEMINI_API_KEY[:10]}...")

# FIX V9 - PAKAI MODEL YANG MASIH HIDUP!
# gemini-1.5-flash udah mati di v1beta, ganti ke gemini-2.0-flash atau gemini-1.5-flash-latest dengan API v1
MODEL_NAME = "gemini-2.0-flash"  # PALING STABIL 2026
# alternatif: "gemini-1.5-flash-latest" atau "gemini-2.5-flash"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Test model list
        model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"GEMINI READY MODEL: {MODEL_NAME}")
    except Exception as e:
        logger.error(f"GEMINI CONFIG ERR: {e}")

# Check ffmpeg & yt-dlp
FFMPEG_OK = shutil.which("ffmpeg") is not None
YTDLP_OK = False
try:
    import yt_dlp
    YTDLP_OK = True
    logger.info("yt-dlp READY - YOUTUBE DJ READY!")
except:
    logger.warning("yt-dlp not installed")

if not FFMPEG_OK:
    logger.warning("ffmpeg NOT FOUND - audio akan 0 chunks!")
else:
    logger.info("ffmpeg READY!")

# ============== YOUTUBE DJ ==============
def search_youtube(query):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'default_search': 'ytsearch1',
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query} lagu", download=False)
            if 'entries' in info and len(info['entries'])>0:
                return info['entries'][0]
    except Exception as e:
        logger.error(f"YT SEARCH ERR: {e}")
    return None

def download_and_convert(url):
    try:
        tmpdir = tempfile.mkdtemp()
        outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # cari mp3
            for f in os.listdir(tmpdir):
                if f.endswith(".mp3"):
                    path = os.path.join(tmpdir, f)
                    return path, tmpdir, info.get('title','Lagu')
    except Exception as e:
        logger.error(f"YT DL ERR: {e}")
    return None, None, None

# ============== HANDLERS ==============
async def ota_handler(request):
    return web.json_response({
        "firmware": {"version": "2.4.2-amix-v9", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/"}
    })

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("WS CONNECTED")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except:
                    continue

                # Audio dari ESP32
                if data.get("type") == "listen" and data.get("state") == "start":
                    logger.info(f"LISTEN start txt='{data.get('text','')}'")
                    await ws.send_json({"type": "stt", "text": "mendengarkan..."})

                if "audio" in data:
                    # ini audio opus dari device, kita proses STT sederhana -> langsung ke Gemini
                    # Untuk V9, kita pakai text dari STT yang dikirim device, atau dummy
                    pass

                # Text langsung (dari device setelah STT)
                if data.get("type") == "text" or "text" in data:
                    user_text = data.get("text") or data.get("data") or ""
                    user_text = str(user_text).strip()
                    if not user_text:
                        continue

                    logger.info(f"USER TEXT: {user_text}")

                    # CEK APAKAH MINTA LAGU?
                    is_music = any(k in user_text.lower() for k in ["putar", "play", "lagu", "musik", "komang", "bernadya", "juicy", "dj"])
                    
                    if is_music and YTDLP_OK and FFMPEG_OK:
                        await ws.send_json({"type": "tts", "state": "start", "text": f"Siap, putar lagu {user_text}, bos!"})
                        # Search YT
                        entry = search_youtube(user_text)
                        if entry:
                            url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                            mp3_path, tmpdir, title = download_and_convert(url)
                            if mp3_path:
                                # convert mp3 ke opus 16k untuk xiaozhi
                                opus_path = mp3_path.replace(".mp3",".opus")
                                subprocess.run(["ffmpeg","-y","-i",mp3_path,"-ar","16000","-ac","1","-c:a","libopus",opus_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                # kirim audio
                                with open(opus_path,"rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                    await ws.send_json({"type": "audio", "audio": b64, "format": "opus", "sample_rate": 16000})
                                shutil.rmtree(tmpdir, ignore_errors=True)
                                await ws.send_json({"type": "tts", "state": "stop"})
                                logger.info(f"YT PLAYED: {title}")
                                continue
                        await ws.send_json({"type": "tts", "state": "stop", "text": "Waduh, lagu gak ketemu bos, coba judul lain!"})
                        continue

                    # JIKA BUKAN LAGU -> GEMINI AI
                    try:
                        model = genai.GenerativeModel(MODEL_NAME)
                        response = await asyncio.to_thread(model.generate_content, f"Kamu adalah Siaga, asisten Amix Kuningan dari Jawa Barat, jawab singkat santai Sunda, user bilang: {user_text}")
                        ai_text = response.text.strip()
                        logger.info(f"GEMINI OK: {ai_text[:80]}")
                        await ws.send_json({"type": "tts", "state": "start"})
                        await ws.send_json({"type": "tts", "state": "sentence_start", "text": ai_text})
                        # TTS pakai edge atau dummy audio? Untuk sekarang kirim text aja, device akan TTS sendiri
                        await ws.send_json({"type": "tts", "state": "stop"})
                    except Exception as e:
                        logger.error(f"GEMINI ERR {e}")
                        await ws.send_json({"type": "tts", "state": "start", "text": "Waduh error bos, coba lagi!"})
                        await ws.send_json({"type": "tts", "state": "stop"})

            elif msg.type == web.WSMsgType.BINARY:
                logger.info(f"AUDIO BINARY {len(msg.data)} bytes")
                # disini seharusnya STT, tapi untuk fix cepat kita anggap device sudah STT sendiri

    except Exception as e:
        logger.error(f"WS ERR {e}")
    finally:
        logger.info("WS DISCONNECTED")
    return ws

app = web.Application()
app.router.add_get("/xiaozhi/ota/", ota_handler)
app.router.add_post("/xiaozhi/ota/", ota_handler)
app.router.add_get("/xiaozhi/v1/", websocket_handler)
app.router.add_get("/", lambda r: web.Response(text="Amix Kuningan Cloud V9 YOUTUBE DJ READY"))

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT","8080")))
