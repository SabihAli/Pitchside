import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class Settings:
    def __init__(self) -> None:
        self.retrieval_service_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8085")
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8083")


settings = Settings()

INGEST_ASYNC_IMAGE_THRESHOLD = int(os.getenv("INGEST_ASYNC_IMAGE_THRESHOLD", "3"))
CHUNK_TARGET_TOKENS = int(os.getenv("CHUNK_TARGET_TOKENS", "400"))
CHUNK_OVERLAP_SENTENCES = int(os.getenv("CHUNK_OVERLAP_SENTENCES", "2"))
TABLE_CHUNK_ROWS = int(os.getenv("TABLE_CHUNK_ROWS", "10"))


class IngestSettings:
    def __init__(self) -> None:
        self.ingest_image_delay_ms = int(os.getenv("INGEST_IMAGE_DELAY_MS", "500"))
        self.ingest_ocr_enabled = os.getenv("INGEST_OCR_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.ingest_ocr_min_confidence = int(os.getenv("INGEST_OCR_MIN_CONFIDENCE", "60"))


ingest_settings = IngestSettings()

# Backward-compatible module-level aliases
INGEST_IMAGE_DELAY_MS = ingest_settings.ingest_image_delay_ms
INGEST_OCR_ENABLED = ingest_settings.ingest_ocr_enabled
INGEST_OCR_MIN_CONFIDENCE = ingest_settings.ingest_ocr_min_confidence
