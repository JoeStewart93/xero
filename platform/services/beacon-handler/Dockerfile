FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/common/python

WORKDIR /app

COPY common/python ./common/python
COPY services/beacon-handler/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/beacon-handler/xero_beacon_handler ./xero_beacon_handler

EXPOSE 8000

CMD ["uvicorn", "xero_beacon_handler.main:app", "--host", "0.0.0.0", "--port", "8000"]
