FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY packages/futbot-common packages/futbot-common
RUN pip install --no-cache-dir -r requirements.txt

COPY services/retrieval services/retrieval
COPY services/ingestion/chunking services/ingestion/chunking
COPY services/ingestion/types.py services/ingestion/types.py
COPY services/ingestion/__init__.py services/ingestion/__init__.py
COPY services/__init__.py services/__init__.py

ENV PYTHONPATH=/app
CMD ["uvicorn", "services.retrieval.main:app", "--host", "0.0.0.0", "--port", "8085"]
