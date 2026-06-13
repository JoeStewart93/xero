FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/common/python

WORKDIR /app

COPY common/python ./common/python
COPY services/scanner/requirements.txt ./requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl dnsutils masscan nmap \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY services/scanner/xero_scanner ./xero_scanner

EXPOSE 8000

CMD ["uvicorn", "xero_scanner.main:app", "--host", "0.0.0.0", "--port", "8000"]
