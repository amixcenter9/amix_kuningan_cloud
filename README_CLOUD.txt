
CARA DEPLOY KE RAILWAY.APP (GRATIS 24 JAM):

1. Buka railway.app -> Login pakai Github
2. Klik New Project -> Deploy from GitHub repo
   ATAU klik "Deploy from local" -> upload file-file ini
3. Railway akan otomatis install requirements.txt
4. Setelah deploy, klik Settings -> Generate Domain
   Nanti dapat link misal: amix-kuningan.up.railway.app
5. URL untuk ESP32 jadi:
   wss://amix-kuningan.up.railway.app/xiaozhi/v1/
   (pakai wss, bukan ws, karena cloud pakai https)

6. Masukin URL itu ke setting ESP32 192.168.4.1

SELESAI! Matikan HP dan komputer pun AMIX_AI tetap jalan!
