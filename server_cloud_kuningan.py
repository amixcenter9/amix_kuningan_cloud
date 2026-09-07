from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, uuid, asyncio, os, time, re
import shutil

print("=== AMIX AI CENTER V8 - AI + YOUTUBE DJ ===")

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except: HAS_GEMINI=False

try:
    import edge_tts
    HAS_TTS=True
except: HAS_TTS=False

try:
    import yt_dlp
    HAS_YT=True
    print("yt-dlp READY - YOUTUBE DJ READY!")
except: 
    HAS_YT=False
    print("yt-dlp not installed")

app = FastAPI(title="AMIX V8 HYBRID AI + YOUTUBE")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip()
print(f"KEY LEN: {len(GEMINI_API_KEY)}")

model=None
if HAS_GEMINI and len(GEMINI_API_KEY)>20:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model=genai.GenerativeModel('gemini-1.5-flash')
        print(">>> GEMINI READY <<<")
    except Exception as e:
        print(f"GEMINI FAIL {e}")

def is_music_request(text: str) -> tuple[bool, str]:
    low=text.lower()
    triggers=["putar","play","putar lagu","play lagu","putarkan","setel","muter","lagu","music","song"]
    if any(t in low for t in triggers):
        # ambil judul lagu
        # hapus kata pemicu
        query = text.lower()
        for t in ["putar lagu","play lagu","putar","play","putarkan","setel lagu","setel","muter lagu","muter","tolong putar","coba putar"]:
            query = query.replace(t,"")
        query = query.strip()
        if not query:
            query = text
        # stop command
        if "stop" in low or "berhenti" in low or "pause" in low:
            return (False, "STOP")
        return (True, query.strip())
    return (False, "")

async def ask_gemini(txt):
    q=txt.lower()
    if model:
        try:
            prompt=f"Kamu Siaga Amix AI Center Ti Kuningan Pikeun Dunia. Jawab singkat 2 kalimat Sunda gaul. User: {txt}. Konteks Ciremai 3078mdpl."
            r=model.generate_content(prompt)
            return r.text.strip()[:350]
        except Exception as e:
            print(f"GEMINI ERR {e}")
    if "ciremai" in q: return "Gunung Ciremai 3078 mdpl bos, tertinggi Jabar! Jalur Palutungan favorit Kuningan!"
    if "halo" in q or len(q)<4: return "Halo bos! Abdi Siaga Amix AI Center! Ti Kuningan Pikeun Dunia! Kumaha damang?"
    return f"Siap bos! Soal '{txt}' - Ti Kuningan Pikeun Dunia!"

async def text_to_opus(text):
    if shutil.which("ffmpeg") is None: return []
    if not HAS_TTS: return []
    import tempfile, subprocess
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp: mp3=tmp.name
        comm=edge_tts.Communicate(text, "id-ID-GadisNeural", rate="-2%")
        await comm.save(mp3)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp: opus=tmp.name
        subprocess.run(["ffmpeg","-y","-i",mp3,"-c:a","libopus","-ar","24000","-ac","1","-b:a","24k",opus], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        data=b""
        if os.path.exists(opus):
            with open(opus,"rb") as f: data=f.read()
        for p in [mp3,opus]:
            try: os.unlink(p)
            except: pass
        if not data: return []
        return [data[i:i+3000] for i in range(0,len(data),3000)]
    except: return []

async def youtube_to_opus_chunks(query: str):
    """Download youtube audio dan convert ke opus chunks"""
    if not HAS_YT:
        print("YT not available")
        return [], "yt-dlp belum install bos"
    if shutil.which("ffmpeg") is None:
        return [], "ffmpeg belum ada bos"
    
    import tempfile
    print(f">>> YOUTUBE SEARCH: {query}")
    try:
        # Cari dan download audio terbaik
        tmp_dir = tempfile.gettempdir()
        output_template = os.path.join(tmp_dir, f"yt_{uuid.uuid4().hex}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1:',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info:
                info = info['entries'][0]
            title = info.get('title','Lagu')
            # file mp3 hasil
            mp3_file = ydl.prepare_filename(info).rsplit('.',1)[0] + '.mp3'
            print(f">>> DOWNLOADED: {title} -> {mp3_file}")
            
            if not os.path.exists(mp3_file):
                # coba cari file mp3 di tmp
                import glob
                files = glob.glob(os.path.join(tmp_dir, "yt_*.mp3"))
                if files:
                    mp3_file = files[-1]
                else:
                    return [], f"Gagal download {query}"
            
            # Convert mp3 ke opus chunks
            with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp: opus_path=tmp.name
            cmd=["ffmpeg","-y","-i",mp3_file,"-c:a","libopus","-ar","24000","-ac","1","-b:a","32k",opus_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            
            data=b""
            if os.path.exists(opus_path):
                with open(opus_path,"rb") as f: data=f.read()
            
            # cleanup
            for p in [mp3_file, opus_path]:
                try: os.unlink(p)
                except: pass
            
            if not data:
                return [], f"Gagal convert {title}"
            
            chunks=[data[i:i+4000] for i in range(0,len(data),4000)]
            print(f">>> YT CHUNKS {len(chunks)} for {title}")
            return chunks, title
            
    except Exception as e:
        print(f"YT ERROR {e}")
        import traceback
        traceback.print_exc()
        return [], f"Error YouTube: {str(e)[:100]}"

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota(request: Request):
    return JSONResponse({
        "firmware":{"version":"8.0-hybrid-youtube","url":""},
        "websocket":{"url":"wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/","token":""},
        "server_time":{"timestamp":0,"timezone_offset":420}
    })

@app.get("/")
def root():
    return {"status":"AMIX V8 HYBRID AI+YOUTUBE","gemini":bool(model),"yt":HAS_YT,"ffmpeg":bool(shutil.which("ffmpeg")),"key_len":len(GEMINI_API_KEY)}

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id=str(uuid.uuid4())
    hello={"type":"hello","transport":"websocket","session_id":session_id,"audio_params":{"format":"opus","sample_rate":24000,"channels":1,"frame_duration":60}}
    await websocket.send_text(json.dumps(hello))
    print(f"CONNECTED {session_id}")

    is_playing_music=False

    async def send_ai_response(user_text):
        await websocket.send_text(json.dumps({"type":"stt","text":user_text,"session_id":session_id}))
        await asyncio.sleep(0.2)
        reply=await ask_gemini(user_text)
        await websocket.send_text(json.dumps({"type":"llm","emotion":"happy","text":reply,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"start","session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":reply,"session_id":session_id}))
        chunks=await text_to_opus(reply)
        for c in chunks:
            await websocket.send_bytes(c)
            await asyncio.sleep(0.05)
        if not chunks: await asyncio.sleep(0.8)
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_end","text":reply,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))

    async def play_youtube(query):
        nonlocal is_playing_music
        is_playing_music=True
        # 1. Bilang dulu mau muter
        say = f"Oke bos! Muter lagu {query} dari YouTube, bentar ya!"
        await websocket.send_text(json.dumps({"type":"stt","text":f"Putar {query}","session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"llm","emotion":"happy","text":say,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"start","session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":say,"session_id":session_id}))
        chunks_say=await text_to_opus(say)
        for c in chunks_say:
            await websocket.send_bytes(c)
            await asyncio.sleep(0.05)
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_end","text":say,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))
        
        # 2. Download YouTube
        await asyncio.sleep(0.5)
        await websocket.send_text(json.dumps({"type":"tts","state":"start","session_id":session_id}))
        yt_chunks, title = await youtube_to_opus_chunks(query)
        
        if not yt_chunks:
            err_text=f"Waduh bos, gagal muter {query} - {title}"
            await websocket.send_text(json.dumps({"type":"llm","text":err_text,"session_id":session_id}))
            await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":err_text,"session_id":session_id}))
            err_chunks=await text_to_opus(err_text)
            for c in err_chunks: 
                await websocket.send_bytes(c)
                await asyncio.sleep(0.05)
            await websocket.send_text(json.dumps({"type":"tts","state":"sentence_end","text":err_text,"session_id":session_id}))
            await websocket.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))
            is_playing_music=False
            return
        
        # 3. Putar lagu YouTube
        play_text=f"Nih bos lagu {title} dari YouTube!"
        await websocket.send_text(json.dumps({"type":"llm","text":play_text,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":play_text,"session_id":session_id}))
        print(f">>> PLAYING YOUTUBE {title} {len(yt_chunks)} chunks")
        for c in yt_chunks:
            if not is_playing_music: 
                print("STOPPED MUSIC")
                break
            await websocket.send_bytes(c)
            await asyncio.sleep(0.08)  # tempo lagu
        
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_end","text":play_text,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))
        is_playing_music=False

    await asyncio.sleep(0.8)
    await send_ai_response("Halo bos")

    audio_chunks=[]
    last_audio=time.time()
    responded=False

    async def auto_responder():
        nonlocal audio_chunks, last_audio, responded
        while True:
            await asyncio.sleep(0.3)
            if audio_chunks and (time.time()-last_audio>1.2) and not responded:
                responded=True
                # Untuk sekarang karena STT masih belum ada Whisper, kita anggap user bilang "Gunung Ciremai"
                # Nanti bos bisa ganti dengan Whisper beneran, tapi untuk test YouTube:
                # Coba deteksi apakah ada kata putar lagu di STT manual
                await send_ai_response("Gunung Ciremai")
                audio_chunks=[]

    asyncio.create_task(auto_responder())

    while True:
        try:
            data=await websocket.receive()
            if "bytes" in data and data["bytes"]:
                audio_chunks.append(data["bytes"])
                last_audio=time.time()
                responded=False
                if len(audio_chunks)==1: print("AUDIO START")
            elif "text" in data:
                try: msg=json.loads(data["text"])
                except: continue
                mtype=msg.get("type","")
                if mtype=="hello":
                    await websocket.send_text(json.dumps(hello))
                elif mtype=="listen":
                    state=msg.get("state")
                    txt=msg.get("text","").strip()
                    print(f"LISTEN {state} txt='{txt}'")
                    if state=="start":
                        audio_chunks=[]
                        responded=False
                        if is_playing_music:
                            is_playing_music=False
                            print("MUSIC STOPPED BY NEW LISTEN")
                    elif state in ["stop","detect"]:
                        if txt:
                            # CEK APAKAH PERINTAH MUSIK?
                            is_music, query = is_music_request(txt)
                            if is_music:
                                await play_youtube(query)
                            elif query=="STOP":
                                is_playing_music=False
                                await send_ai_response("Oke stop musiknya bos!")
                            else:
                                await send_ai_response(txt)
                        elif audio_chunks and not responded:
                            responded=True
                            await send_ai_response("Halo bos")
                        audio_chunks=[]
                elif mtype=="text":
                    txt=msg.get("text","")
                    is_music, query = is_music_request(txt)
                    if is_music:
                        await play_youtube(query)
                    elif query=="STOP":
                        is_playing_music=False
                        await send_ai_response("Oke stop musiknya bos!")
                    else:
                        await send_ai_response(txt)
                elif mtype=="abort":
                    audio_chunks=[]
                    responded=False
                    is_playing_music=False
        except Exception as e:
            print(f"WS END {e}")
            break
