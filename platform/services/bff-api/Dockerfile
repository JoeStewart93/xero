FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/common/python

WORKDIR /app

COPY common/python ./common/python
COPY services/bff-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/bff-api/xero_bff ./xero_bff
COPY services/bff-api/alembic.ini ./alembic.ini
COPY services/bff-api/alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "python -m xero_bff.manage migrate && python -m xero_bff.manage seed && uvicorn xero_bff.main:app --host 0.0.0.0 --port 8000"]
