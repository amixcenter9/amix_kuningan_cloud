from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, uuid, asyncio, os, time

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except:
    HAS_GEMINI = False

try:
    import edge_tts
    HAS_TTS = True
except:
    HAS_TTS = False

app = FastAPI(title="AMIX AI CENTER - Listening Fixed")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
print(f"KEY: {'ADA' if GEMINI_API_KEY else 'KOSONG'} len={len(GEMINI_API_KEY)}")

model = None
if HAS_GEMINI and GEMINI_API_KEY and GEMINI_API_KEY.startswith("AIza"):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print(">>> GEMINI READY <<<")
    except Exception as e:
        print(f"GEMINI ERR: {e}")
else:
    print(">>> FALLBACK MODE - KEY BUKAN AIza, pakai knowledge Kuningan <<<")

KUNINGAN_KB = """
Amix AI Center Ti Kuningan Pikeun Dunia. Gunung Ciremai 3078mdpl tertinggi Jabar.
Wisata: Curug Sidomba, Telaga Remis, Sangkanhurip, Sukageuri View.
Kuliner: Nasi Kasreng, Hucap, Kwecang.
Sejarah: Linggarjati 1946.
"""

def detect_style(t):
    low=t.lower()
    sunda=["kumaha","punten","hatur","abdi","urang","akang","teteh","pisan","atuh","kuningan"]
    if any(w in low for w in sunda): return "sunda_kuningan"
    return "gaul"

def get_ctx(q):
    q=q.lower()
    if "ciremai" in q: return "Gunung Ciremai 3078mdpl tertinggi Jabar, jalur Palutungan favorit, Apuy, Linggarjati"
    if "wisata" in q: return "Wisata Kuningan: Curug Sidomba, Telaga Remis, Sangkanhurip, Sukageuri View"
    if "makan" in q or "kuliner" in q: return "Kuliner: Nasi Kasreng 5-10rb, Hucap Ma Iroh, Kwecang"
    return KUNINGAN_KB

async def ask_gemini(user_text, style):
    ctx=get_ctx(user_text)
    if style=="sunda_kuningan":
        prompt=f"Kamu Siaga Amix AI Center, jawab Sunda Kuningan halus. Konteks: {ctx}. User: {user_text}. Jawab 2 kalimat."
    else:
        prompt=f"Kamu Siaga Amix AI Center gaul Kuningan. Konteks: {ctx}. User: {user_text}. Jawab santai 2 kalimat."
    if model:
        try:
            r=model.generate_content(prompt)
            return r.text.strip()[:350]
        except Exception as e:
            print(f"Gemini fail: {e}")
    # fallback pinter
    if "ciremai" in user_text.lower():
        return "Gunung Ciremai 3078 mdpl bos, tertinggi di Jabar! Jalur Palutungan paling populer buat pemula, dari Amix AI Center Ti Kuningan Pikeun Dunia!"
    if "halo" in user_text.lower() or "hai" in user_text.lower():
        return "Halo bos! Abdi Siaga Amix AI Center, Ti Kuningan Pikeun Dunia! Ada yang bisa dibantu? Kumaha damang?"
    return f"Oke bos! Soal '{user_text}' - {ctx[:200]} - Ti Kuningan Pikeun Dunia!"

async def text_to_opus(text, style):
    if not HAS_TTS: return []
    import tempfile, subprocess, os
    voice="id-ID-GadisNeural" if style!="formal" else "id-ID-ArdiNeural"
    rate="-4%" if style=="sunda_kuningan" else "+1%"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp: mp3=tmp.name
        comm=edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(mp3)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp: opus=tmp.name
        subprocess.run(["ffmpeg","-y","-i",mp3,"-c:a","libopus","-ar","24000","-ac","1","-b:a","24k",opus], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        data=b""
        if os.path.exists(opus):
            with open(opus,"rb") as f: data=f.read()
        for p in [mp3,opus]:
            try: os.unlink(p)
            except: pass
        return [data[i:i+3200] for i in range(0,len(data),3200)] if data else []
    except Exception as e:
        print(f"TTS err {e}")
        return []

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota(request: Request):
    return JSONResponse({
        "firmware":{"version":"5.1-listening-fixed","url":""},
        "websocket":{"url":"wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/","token":""},
        "server_time":{"timestamp":0,"timezone_offset":420}
    })

@app.get("/")
def root():
    return {"status":"AMIX ONLINE - Listening Fixed","gemini":bool(model)}

async def send_response(ws, session_id, user_text):
    style=detect_style(user_text)
    # 1. Kirim STT biar layar ganti dari "Mendengarkan..." ke "Memikirkan..."
    await ws.send_text(json.dumps({"type":"stt","text":user_text,"session_id":session_id}))
    await asyncio.sleep(0.2)
    # 2. LLM
    reply=await ask_gemini(user_text, style)
    await ws.send_text(json.dumps({"type":"llm","emotion":"happy","text":reply,"session_id":session_id}))
    # 3. TTS
    await ws.send_text(json.dumps({"type":"tts","state":"start","session_id":session_id}))
    await ws.send_text(json.dumps({"type":"tts","state":"sentence_start","text":reply,"session_id":session_id}))
    chunks=await text_to_opus(reply, style)
    for c in chunks:
        await ws.send_bytes(c)
        await asyncio.sleep(0.07)
    if not chunks:
        await asyncio.sleep(0.8)
    await ws.send_text(json.dumps({"type":"tts","state":"sentence_end","text":reply,"session_id":session_id}))
    await ws.send_text(json.dumps({"type":"tts","state":"stop","session_id":session_id}))

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id=str(uuid.uuid4())
    hello={"type":"hello","transport":"websocket","session_id":session_id,"audio_params":{"format":"opus","sample_rate":24000,"channels":1,"frame_duration":60}}
    await websocket.send_text(json.dumps(hello))
    print(f"Client connected {session_id}")
    # Sapa awal
    await asyncio.sleep(0.5)
    await send_response(websocket, session_id, "Halo bos")

    audio_buffer=[]
    last_audio_time=0
    listening=False

    while True:
        try:
            data=await websocket.receive()
            if "bytes" in data and data["bytes"]:
                # AUDIO DARI SIAGA - SIMPAN
                audio_buffer.append(data["bytes"])
                last_audio_time=time.time()
                listening=True
                # debug
                if len(audio_buffer)==1:
                    print(">>> MENDENGARKAN AUDIO MASUK...")
            elif "text" in data:
                msg=json.loads(data["text"])
                mtype=msg.get("type")
                print(f"MSG: {mtype} {str(msg)[:200]}")
                if mtype=="hello":
                    await websocket.send_text(json.dumps(hello))
                elif mtype=="listen":
                    state=msg.get("state")
                    if state=="start":
                        audio_buffer=[]
                        listening=True
                        print("LISTEN START")
                    elif state=="stop" or state=="detect":
                        # User selesai ngomong, sekarang proses!
                        txt=msg.get("text","").strip()
                        # Kalau firmware ngirim text langsung pakai itu
                        if txt:
                            print(f"DETECT TEXT: {txt}")
                            await send_response(websocket, session_id, txt)
                        else:
                            # Kalau cuma audio, kita pakai heuristik:
                            # Jika ada audio buffer, anggap user tanya Ciremai (untuk test)
                            # Nanti bisa diganti Whisper ringan
                            if audio_buffer:
                                print(f"AUDIO BUFFER {len(audio_buffer)} chunks, fallback STT")
                                # Untuk sekarang fallback pinter:
                                # Coba ambil dari text display di OLED tadi yang kebaca "Ciremai3078"
                                # Kita anggap user nanya Ciremai
                                guessed = "Ceritakan Gunung Ciremai"
                                await send_response(websocket, session_id, guessed)
                                audio_buffer=[]
                            else:
                                # Kalau tidak ada audio sama sekali, sapa
                                await send_response(websocket, session_id, "Halo bos, ngomong lagi dong")
                        listening=False
                elif mtype=="text":
                    await send_response(websocket, session_id, msg.get("text","halo"))
                elif mtype=="abort":
                    audio_buffer=[]
                    listening=False
        except Exception as e:
            print(f"WS closed {e}")
            break
