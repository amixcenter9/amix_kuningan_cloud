from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
import json, uuid, asyncio, os
from pathlib import Path

# GEMINI ONLY - RINGAN, TIDAK CRASH
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

app = FastAPI(title="AMIX AI CENTER - Light Gemini Stable")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
print(f"KEY CHECK: {'ADA' if GEMINI_API_KEY else 'KOSONG'} length={len(GEMINI_API_KEY)}")

if HAS_GEMINI and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print(">>> GEMINI READY - AMIX AI CENTER ONLINE <<<")
    except Exception as e:
        print(f"GEMINI CONFIG ERROR: {e}")
        model = None
else:
    model = None
    print(">>> MODE FALLBACK KUNINGAN - KEY BELUM VALID <<<")

KUNINGAN_KB = """
AMIX AI CENTER - Ti Kuningan Pikeun Dunia
- Gunung Ciremai 3078 mdpl tertinggi Jabar, jalur Palutungan populer
- Wisata: Curug Sidomba, Telaga Remis, Sangkanhurip, Bukit Panembongan, Sukageuri View
- Sejarah: Linggarjati 1946, Cipari 4500 tahun, hari jadi 1 Sept 1498
- Kuliner: Nasi Kasreng, Hucap Ma Iroh, Kwecang, Tahu Kopeci, Tape Ketan
- 32 Kecamatan, bahasa Sunda Kuningan: punten, hatur nuhun, kumaha damang
"""

def detect_style(text: str) -> str:
    SUNDA = ["kumaha", "punten", "hatur", "abdi", "urang", "akang", "teteh", "aing", "pisan", "atuh", "kuningan"]
    FORMAL = ["bapak", "ibu", "mohon", "terima kasih"]
    low = text.lower()
    if any(w in low for w in SUNDA):
        return "sunda_kuningan"
    if any(w in low for w in FORMAL):
        return "formal"
    return "gaul"

def get_ctx(q: str) -> str:
    q = q.lower()
    if "ciremai" in q or "gunung" in q: return "Gunung Ciremai 3078mdpl tertinggi Jabar, Palutungan favorit pemula, Apuy, Linggarjati tertua"
    if "wisata" in q: return "Wisata Kuningan: Curug Sidomba, Telaga Remis, Sangkanhurip air panas, Sukageuri View, Kebun Raya"
    if "kuliner" in q or "makan" in q: return "Kuliner: Nasi Kasreng Rp5-10rb, Hucap Ma Iroh, Kwecang, Tahu Kopeci Kuningan"
    if "sejarah" in q: return "Sejarah: Perundingan Linggarjati 1946, Situs Cipari 4500 tahun, hari jadi 1 Sept 1498"
    return KUNINGAN_KB[:1200]

async def ask_gemini(user_text: str, style: str) -> str:
    ctx = get_ctx(user_text)
    if style == "sunda_kuningan":
        sys_prompt = f"Kamu Siaga, asisten Amix AI Center - Ti Kuningan Pikeun Dunia. Jawab Sunda Kuningan halus + Indonesia, ramah. Konteks Kuningan: {ctx}. Jawab singkat 2 kalimat, akurat kayak Gemini."
    elif style == "formal":
        sys_prompt = f"Anda Siaga, Amix AI Center Kuningan. Jawab formal. Konteks: {ctx}. Singkat akurat."
    else:
        sys_prompt = f"Kamu Siaga, asisten Amix AI Center gaul Kuningan. Konteks: {ctx}. Jawab santai gaul singkat."

    full_prompt = f"{sys_prompt}\nUser: {user_text}\nSiaga:"

    if model:
        try:
            resp = model.generate_content(full_prompt)
            txt = resp.text.strip()
            print(f"GEMINI OK: {txt[:100]}")
            return txt[:400]
        except Exception as e:
            print(f"GEMINI ERROR: {e}")

    # Fallback kalau Gemini error / key salah format
    if style == "sunda_kuningan":
        return f"Punten bos, abdi Siaga Amix AI Center. Soal '{user_text}' - ieu Kuningan: {ctx[:200]}"
    return f"Oke bos! Amix AI Center - Ti Kuningan Pikeun Dunia! Soal '{user_text}' : {ctx[:200]}"

async def text_to_opus(text: str, style: str) -> list[bytes]:
    if not HAS_TTS:
        return []
    import tempfile, subprocess, os
    voice = "id-ID-GadisNeural" if style != "formal" else "id-ID-ArdiNeural"
    rate = "-5%" if style=="sunda_kuningan" else ("-2%" if style=="formal" else "+2%")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
            mp3_path = tmp_mp3.name
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(mp3_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp_opus:
            opus_path = tmp_opus.name
        cmd = ["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus", "-ar", "24000", "-ac", "1", "-b:a", "24k", opus_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        data = b""
        if os.path.exists(opus_path):
            with open(opus_path, "rb") as f:
                data = f.read()
        for p in [mp3_path, opus_path]:
            try: os.unlink(p)
            except: pass
        return [data[i:i+3000] for i in range(0, len(data), 3000)] if data else []
    except Exception as e:
        print(f"TTS err: {e}")
        return []

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
async def ota(request: Request):
    return JSONResponse({
        "firmware": {"version": "5.0-gemini-light-stable", "url": ""},
        "websocket": {"url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/", "token": ""},
        "server_time": {"timestamp": 0, "timezone_offset": 420}
    })

@app.get("/")
def root():
    return {"name": "AMIX AI CENTER", "tagline": "Ti Kuningan Pikeun Dunia", "gemini": bool(model), "status": "STABLE LIGHT VERSION"}

async def handle_text(websocket: WebSocket, session_id: str, user_text: str):
    style = detect_style(user_text)
    reply = await ask_gemini(user_text, style)
    await websocket.send_text(json.dumps({"type": "llm", "emotion": "happy", "text": reply, "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "start", "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply, "session_id": session_id}))
    chunks = await text_to_opus(reply, style)
    for c in chunks:
        await websocket.send_bytes(c)
        await asyncio.sleep(0.06)
    if not chunks:
        await asyncio.sleep(0.7)
    await websocket.send_text(json.dumps({"type": "tts", "state": "sentence_end", "text": reply, "session_id": session_id}))
    await websocket.send_text(json.dumps({"type": "tts", "state": "stop", "session_id": session_id}))

@app.websocket("/xiaozhi/v1/")
@app.websocket("/xiaozhi/v1")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    hello = {"type": "hello", "transport": "websocket", "session_id": session_id, "audio_params": {"format": "opus", "sample_rate": 24000, "channels": 1, "frame_duration": 60}}
    await websocket.send_text(json.dumps(hello))
    await asyncio.sleep(0.3)
    await handle_text(websocket, session_id, "Halo bos Amix AI Center online")
    while True:
        try:
            data = await websocket.receive()
            if "text" in data:
                msg = json.loads(data["text"])
                mtype = msg.get("type")
                if mtype == "hello":
                    await websocket.send_text(json.dumps(hello))
                elif mtype == "listen":
                    state = msg.get("state")
                    if state == "detect":
                        txt = msg.get("text","")
                        if txt:
                            await handle_text(websocket, session_id, txt)
                elif mtype == "text":
                    await handle_text(websocket, session_id, msg.get("text",""))
        except Exception as e:
            print(f"WS closed: {e}")
            break
