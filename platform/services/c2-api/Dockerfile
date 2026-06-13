FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/common/python

WORKDIR /app

COPY common/python ./common/python
COPY services/c2-api/requirements.txt ./requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl dnsutils docker.io docker-compose masscan nmap \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY services/c2-api/xero_c2 ./xero_c2
COPY services/c2-api/alembic.ini ./alembic.ini
COPY services/c2-api/alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "python -m xero_c2.manage migrate && uvicorn xero_c2.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval ${C2_BEACON_WS_PING_INTERVAL_SECONDS:-30} --ws-ping-timeout ${C2_BEACON_WS_PING_TIMEOUT_SECONDS:-30} --ws-max-size ${C2_BEACON_WS_MAX_MESSAGE_BYTES:-1048576}"]
