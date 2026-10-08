FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-docker.txt .
COPY packages/futbot-common packages/futbot-common
RUN pip install --no-cache-dir -r requirements-docker.txt \
    && python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Copy source code
COPY . .

# Default command
CMD ["pytest"]
