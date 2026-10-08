FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY packages/futbot-common packages/futbot-common
RUN pip install --no-cache-dir -r requirements.txt

COPY services/tools services/tools
COPY services/__init__.py services/__init__.py

ENV PYTHONPATH=/app
CMD ["uvicorn", "services.tools.main:app", "--host", "0.0.0.0", "--port", "8088"]
