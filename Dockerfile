FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
COPY packages/futbot-common packages/futbot-common
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Copy source code
COPY . .

# Default command
CMD ["pytest"]
