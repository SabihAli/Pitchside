FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY packages/futbot-common packages/futbot-common
RUN pip install --no-cache-dir -r requirements.txt

COPY services/rag_orchestrator services/rag_orchestrator
COPY services/observability/trace_store.py services/observability/trace_store.py
COPY services/observability/config.py services/observability/config.py
COPY services/observability/__init__.py services/observability/__init__.py
COPY services/chat/conversation.py services/chat/conversation.py
COPY services/chat/config.py services/chat/config.py
COPY services/chat/__init__.py services/chat/__init__.py
COPY services/llm_gateway services/llm_gateway
COPY services/__init__.py services/__init__.py

ENV PYTHONPATH=/app
CMD ["uvicorn", "services.rag_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8084"]
