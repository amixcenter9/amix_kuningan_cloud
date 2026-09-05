FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt.
RUN pip install -r requirements.txt
COPY..
CMD uvicorn server_cloud_kuningan:app --host 0.0.0.0 --port $PORT --proxy-headers