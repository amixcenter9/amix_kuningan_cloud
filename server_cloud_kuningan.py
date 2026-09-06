from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, uuid, asyncio, os, time

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except: HAS_GEMINI=False
try:
    import edge_tts
    HAS_TTS=True
except: HAS_TTS=False

app = FastAPI(title="AMIX V2 - Auto Respond")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")
print(f"KEY: {len(GEMINI_API_KEY)}")

model=None
if HAS_GEMINI and GEMINI_API_KEY.startswith("AIza"):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model=genai.GenerativeModel('gemini-1.5-flash')
        print("GEMINI READY")
    except: pass

async def ask_gemini(txt):
    q=txt.lower()
    if model:
        try:
            prompt=f"Kamu Siaga Amix AI Center Ti Kuningan Pikeun Dunia, jawab singkat 2 kalimat gaul Sunda. User: {txt}. Konteks Gunung Ciremai 3078mdpl."
            r=model.generate_content(prompt)
            return r.text.strip()[:350]
        except Exception as e:
            print(f"Gemini err {e}")
    # Fallback super pinter tanpa Gemini
    if "ciremai" in q: return "Gunung Ciremai 3078 mdpl bos, tertinggi di Jawa Barat! Jalur Palutungan paling favorit dari Kuningan, keren pisan!"
    if "halo" in q or "hai" in q or len(q)<3: return "Halo bos! Abdi Siaga Amix AI Center! Ti Kuningan Pikeun Dunia! Kumaha damang?"
    return f"Siap bos! Soal '{txt}' - Amix AI Center Kuningan hadir! Gunung Ciremai 3078 mdpl, wisata Curug Sidomba mantap!"

async def text_to_opus(text):
    if not HAS_TTS: return []
    import tempfile, subprocess
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp: mp3=tmp.name
        comm=edge_tts.Communicate(text, "id-ID-GadisNeural", rate="-2%")
        await comm.save(mp3)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp: opus=tmp.name
        subprocess.run(["ffmpeg","-y","-i",mp3,"-c:a","libopus","-ar","24000","-ac","1","-b:a","24k",opus], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        data=b""
        if os.path.exists(opus):
            with open(opus,"rb") as f: data=f.read()
        for p in [mp3,opus]:
            try: os.unlink(p)
            except: pass
        return [data[i:i+3000] for i in range(0,len(data),3000)] if data else []
    except Exception as e:
        print(f"TTS err {e}")
        return []

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota(request: Request):
    return JSONResponse({
        "firmware":{"version":"6.0-auto-respond","url":""},
        "websocket":{"url":"wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/","token":""},
        "server_time":{"timestamp":0,"timezone_offset":420}
    })

@app.get("/")
def root(): return {"status":"AMIX V2 AUTO RESPON","gemini":bool(model)}

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id=str(uuid.uuid4())
    hello={"type":"hello","transport":"websocket","session_id":session_id,"audio_params":{"format":"opus","sample_rate":24000,"channels":1,"frame_duration":60}}
    await websocket.send_text(json.dumps(hello))
    print(f"CONNECTED {session_id}")

    async def send_response(user_text):
        print(f">>> RESPONDING TO: {user_text}")
        # Biar OLED ganti dari Mendengarkan...
        await websocket.send_text(json.dumps({"type":"stt","text":user_text,"session_id":session_id}))
        await asyncio.sleep(0.15)
        reply=await ask_gemini(user_text)
        print(f">>> REPLY: {reply}")
        await websocket.send_text(json.dumps({"type":"llm","emotion":"happy","text":reply,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"start","session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_start","text":reply,"session_id":session_id}))
        chunks=await text_to_opus(reply)
        print(f">>> SENDING {len(chunks)} audio chunks")
        for c in chunks:
            await websocket.send_bytes(c)
            await asyncio.sleep(0.06)
        if not chunks:
            await asyncio.sleep(0.8)
        await websocket.send_text(json.dumps({"type":"tts","state":"sentence_end","text":reply,"session_id":session_id}))
        await websocket.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))

    # Sapaan awal biar tau speaker jalan
    await asyncio.sleep(0.8)
    await send_response("Halo bos")

    audio_chunks=[]
    last_audio=time.time()
    already_responded=False

    async def auto_check():
        nonlocal audio_chunks, last_audio, already_responded
        while True:
            await asyncio.sleep(0.3)
            if audio_chunks and (time.time()-last_audio>1.0) and not already_responded:
                print(f"AUTO RESPON TRIGGER - {len(audio_chunks)} chunks")
                already_responded=True
                # Untuk sekarang kita anggap tanya Ciremai, nanti diganti Whisper
                await send_response("Gunung Ciremai")
                audio_chunks=[]
    
    asyncio.create_task(auto_check())

    while True:
        try:
            data=await websocket.receive()
            if "bytes" in data and data["bytes"]:
                b=data["bytes"]
                audio_chunks.append(b)
                last_audio=time.time()
                already_responded=False
                if len(audio_chunks)==1:
                    print("AUDIO START")
                # print(f"audio {len(b)} bytes total chunks {len(audio_chunks)}")
            elif "text" in data:
                try:
                    msg=json.loads(data["text"])
                except:
                    continue
                mtype=msg.get("type","")
                # print(f"TEXT MSG {mtype}: {str(msg)[:300]}")
                if mtype=="hello":
                    await websocket.send_text(json.dumps(hello))
                elif mtype=="listen":
                    state=msg.get("state")
                    txt=msg.get("text","").strip()
                    print(f"LISTEN {state} text='{txt}' chunks={len(audio_chunks)}")
                    if state=="start":
                        audio_chunks=[]
                        already_responded=False
                        last_audio=time.time()
                    elif state in ["stop","detect"]:
                        if txt:
                            await send_response(txt)
                        elif audio_chunks and not already_responded:
                            already_responded=True
                            await send_response("Halo Siaga")
                        audio_chunks=[]
                elif mtype=="text":
                    await send_response(msg.get("text","halo"))
                elif mtype=="abort":
                    audio_chunks=[]
                    already_responded=False
        except Exception as e:
            print(f"WS END {e}")
            break
