from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
def root():
    return {"status": "AMIX Kuningan Cloud v2.4.2 Siaga"}

@app.get("/xiaozhi/ota/")
@app.post("/xiaozhi/ota/")
def ota():
    return {
        "firmware": {
            "version": "2.4.2-amix-kuningan",
            "url": ""
        },
        "websocket": {
            "url": "wss://amixkuningancloud-production.up.railway.app/xiaozhi/v1/",
            "token": ""
        },
        "server_time": {
            "timestamp": 0,
            "timezone_offset": 420
        }
    }

# Biar gak 404 pas aktivasi
@app.post("/activate")
def activate():
    return {"code": 0}
