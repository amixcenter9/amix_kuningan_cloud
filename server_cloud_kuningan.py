from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, uuid, asyncio, os, re, tempfile, subprocess
from pathlib import Path

# GEMINI
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except:
    HAS_GEMINI = False

# TTS
try:
    import edge_tts
    HAS_TTS = True
except:
    HAS_TTS = False

# WHISPER (STT)
try:
    import whisper
    whisper_model = whisper.load_model("base")  # base = akurat & ringan, bisa Sunda & Indonesia
    HAS_WHISPER = True
    print("Whisper loaded: base")
except Exception as e:
    print(f"Whisper not loaded: {e}")
    whisper_model = None
    HAS_WHISPER = False

app = FastAPI(title="AMIX AI CENTER - Siaga Gemini + Whisper Final")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if HAS_GEMINI and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("GEMINI READY")
else:
    model = None
    print("GEMINI KEY BELUM DI SET - pakai fallback")

KUNINGAN_KB = """
DATABASE KABUPATEN KUNINGAN:
- 32 Kecamatan, 361 Desa, 15 Kelurahan, luas 1.194 km2, hari jadi 1 Sept 1498
- Gunung Ciremai 3078 mdpl (tertinggi Jabar), jalur Linggarjati (tertua), Apuy, Palutungan (paling populer pemula)
- Wisata: TNGC 64 ODTWA, Curug Sidomba, Telaga Remis, Bukit Panembongan, Sukageuri View, Sangkanhurip air panas, Cibulan, Kebun Raya Kuningan
- Sejarah: Perundingan Linggarjati Nov 1946, Situs Cipari 4500 tahun lalu, Kampung Adat Paseban Cigugur, Seren Taun
- Kuliner: Nasi Kasreng Rp5-10rb ikon, Hucap Ma Iroh Jl Dewi Sartika (tahu kecap ketupat), Kwecang ketan kenyal, Tahu Kopeci, Tape Ketan oleh-oleh, sentra Kertawinangun
- Bahasa Sunda Kuningan medok: punten, hatur nuhun, kumaha damang, abdi, pisan, atuh, teh, mah
"""

def detect_style(text: str) -> str:
    SUNDA = ["kumaha", "punten", "hatur", "abdi", "urang", "akang", "teteh", "aing", "maneh", "pisan", "atuh", "kuningan", "sunda"]
    FORMAL = ["bapak", "ibu", "mohon", "terima kasih", "selamat"]
    low = text.lower()
    if any(w in low for w in SUNDA):
        return "sunda_kuningan"
    if any(w in low for w in FORMAL) or len(text) > 80:
        return "formal"
    return "gaul"

def get_kuningan_context(query: str) -> str:
    q = query.lower()
    ctx = []
    if any(k in q for k in ["wisata", "ciremai", "gunung", "curug", "palutungan"]):
        ctx.append("Wisata: Ciremai 3078mdpl, Palutungan populer, Curug Sidomba, Telaga Remis, Sangkanhurip, Sukageuri View")
    if any(k in q for k in ["sejarah", "linggarjati", "cipari"]):
        ctx.append("Sejarah: Linggarjati 1946, Cipari 4500 tahun, Paseban, hari jadi 1 Sept 1498")
    if any(k in q for k in ["kuliner", "makan", "hucap", "nasi"]):
        ctx.append("Kuliner: Nasi Kasreng, Hucap Ma Iroh, Kwecang, Tahu Kopeci, Tape Ketan")
    if not ctx:
        ctx.append(KUNINGAN_KB[:1500])
    return " | ".join(ctx)

async def ask_gemini(user_text: str, style: str) -> str:
    context = get_kuningan_context(user_text)
    if style == "sunda_kuningan":
        sys_prompt = f"Kamu Siaga, dari Amix AI Center - Ti Kuningan Pikeun Dunia. Jawab Sunda Kuningan halus campur Indonesia, ramah medok. Konteks: {context}. Max 2 kalimat, akurat."
    elif style == "formal":
        sys_prompt = f"Anda Siaga, asisten Amix AI Center - Ti Kuningan Pikeun Dunia. Jawab formal profesional. Konteks: {context}. Singkat akurat."
    else:
        sys_prompt = f"Kamu Siaga, asisten gaul Amix AI Center Kuningan. Jawab santai friendly gaul. Konteks: {context}. Singkat."

    full_prompt = f"{sys_prompt}\nUser: {user_text}\nSiaga:"

    if model:
        try:
            resp = model.generate_content(full_prompt)
            return resp.text.strip()[:350]
        except Exception as e:
            print(f"Gemini err: {e}")

    # Fallback cerdas
    if "wisata" in user_text.lower():
        return "Punten bos, wisata Kuningan aya Gunung Ciremai 3078mdpl jalur Palutungan paling populer, Curug Sidomba, Telaga Remis, sareng Sangkanhurip. Bade kamana bos?" if style=="sunda_kuningan" else "Wisata unggulan Kuningan: Gunung Ciremai 3078mdpl, Palutungan, Curug Sidomba, Telaga Remis, Sangkanhurip."
    return f"Punten bos, abdi Siaga Amix AI Center. Bos nyarios '{user_text}' - Siaga siap bantu, ti Kuningan pikeun dunia!" if style=="sunda_kuningan" else f"Oke bos! Siaga Amix AI Center siap! '{user_text}' - mau dibantu apa?"

def transcribe_opus_to_text(opus_bytes: bytes) -> str:
    """Whisper STT: Opus -> Wav -> Text (bisa Sunda, Indo, Inggris)"""
    if not HAS_WHISPER or not whisper_model:
        return ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as f_opus:
            f_opus.write(opus_bytes)
            opus_path = f_opus.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f_wav:
            wav_path = f_wav.name
        
        # Opus -> Wav 16k mono untuk Whisper
        cmd = ["ffmpeg", "-y", "-i", opus_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        
        # Transcribe
        result = whisper_model.transcribe(wav_path, language=None)  # auto detect: id, su, en
        text = result["text"].strip()
        
        os.unlink(opus_path)
        os.unlink(wav_path)
        print(f"WHISPER: {text}")
        return text
    except Exception as e:
        print(f"Whisper error: {e}")
        return ""

async def text_to_opus(text: str, style: str) -> list[bytes]:
    if not HAS_TTS:
        return []
    voice = "id-ID-GadisNeural" if style != "formal" else "id-ID-ArdiNeural"
    rate = "-5%" if style=="sunda_kuningan" else ("-2%" if style=="formal" else "+4%")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
            mp3_path = tmp_mp3.name
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(mp3_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp_opus:
            opus_path = tmp_opus.name
        cmd = ["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus", "-ar", "24000", "-ac", "1", "-b:a", "24k", opus_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
        if os.path.exists(opus_path):
            with open(opus_path, "rb") as f:
                data = f.read()
            os.unlink(mp3_path)
            os.unlink(opus_path)
            return [data[i:i+3000] for i in range(0, len(data), 3000)]
        os.unlink(mp3_path)
        return []
    except Exception as e:
        print(f"TTS err: {e}")
        return []

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota(request: Request):
    return JSONResponse({
        "firmware": {"version": "4.0-gemini-whisper-final", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/", "token": ""},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/")
def root():
    return {"name": "AMIX AI CENTER - Ti Kuningan Pikeun Dunia", "siaga": "Gemini + Whisper + Kuningan DB", "gemini": bool(model), "whisper": HAS_WHISPER, "tts": HAS_TTS}

async def handle_user_text(websocket: WebSocket, session_id: str, user_text: str):
    style = detect_style(user_text)
    reply = await ask_gemini(user_text, style)
    print(f"[{style}] {user_text} -> {reply}")
    await websocket.send_text(json.dumps({"type": "llm", "emotion": "happy", "text": reply, "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply, "session_id": session_id}))
    chunks = await text_to_opus(reply, style)
    for c in chunks:
        await websocket.send_bytes(c)
        await asyncio.sleep(0.05)
    if not chunks:
        await asyncio.sleep(0.8)
    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": reply, "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    audio_buffer = bytearray()

    hello = {"type": "hello", "transport": "websocket", "session_id": session_id, "audio_params": {"format": "opus", "sample_rate": 24000, "channels": 1, "frame_duration": 60}}
    await websocket.send_text(json.dumps(hello))
    await asyncio.sleep(0.4)
    await handle_user_text(websocket, session_id, "Halo Siaga Amix AI Center")

    while True:
        try:
            data = await websocket.receive()
            if "bytes" in data:
                # Kumpulin audio Opus dari Siaga
                audio_buffer.extend(data["bytes"])
            if "text" in data:
                msg = json.loads(data["text"])
                mtype = msg.get("type")
                if mtype == "hello":
                    await websocket.send_text(json.dumps(hello))
                elif mtype == "listen":
                    state = msg.get("state")
                    if state == "start":
                        audio_buffer = bytearray()  # reset
                    elif state == "stop":
                        # User selesai ngomong -> Whisper STT!
                        if len(audio_buffer) > 1000 and HAS_WHISPER:
                            text_from_speech = transcribe_opus_to_text(bytes(audio_buffer))
                            if text_from_speech:
                                await handle_user_text(websocket, session_id, text_from_speech)
                            else:
                                await handle_user_text(websocket, session_id, "Maaf bos, tidak terdengar jelas, bisa ulangi?")
                        else:
                            # Fallback kalau audio pendek atau whisper belum ready, pakai teks dari device kalau ada
                            fallback_text = msg.get("text", "")
                            if fallback_text:
                                await handle_user_text(websocket, session_id, fallback_text)
                            else:
                                await handle_user_text(websocket, session_id, "Halo, tes Amix AI Center")
                        audio_buffer = bytearray()
                    elif state == "detect":
                        txt = msg.get("text", "")
                        if txt:
                            await handle_user_text(websocket, session_id, txt)
                elif mtype == "text":
                    await handle_user_text(websocket, session_id, msg.get("text",""))
        except Exception as e:
            print(f"WS closed: {e}")
            break
