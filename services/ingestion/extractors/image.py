import logging
import time
from concurrent.futures import ThreadPoolExecutor

from services.ingestion.config import ingest_settings
from services.ingestion.errors import IngestionProviderError, VisionUnavailableError
from services.ingestion.extractors.ocr import ocr_image
from services.ingestion.types import ExtractedBlock
from services.llm_gateway.config import settings as llm_settings
from services.llm_gateway.prompt_loader import get_prompt_parts
from services.llm_gateway.provider import LLM_CALL_FAILED_PREFIX, MODEL_GENERATOR, invoke_llm

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _describe_image(image_bytes: bytes, filename: str = "uploaded image") -> str:
    if llm_settings.llm_provider != "groq":
        raise IngestionProviderError()

    system_prompt, user_prompt = get_prompt_parts("VISION")
    description = invoke_llm(
        prompt=user_prompt,
        model_name=MODEL_GENERATOR,
        step="vision",
        system_prompt=system_prompt,
        image=image_bytes,
    ).strip()
    if description.startswith(LLM_CALL_FAILED_PREFIX):
        # The vision call itself failed (rate limit, outage, etc.) -- invoke_llm
        # returns a human-readable error string here, not a real description.
        # Feeding that into the football-relevance classifier would make an
        # infra failure look like "this image isn't about football".
        raise VisionUnavailableError(filename, description)
    return description


def process_image(image_bytes: bytes, filename: str = "uploaded image") -> str:
    """Two-pass extraction: VLM description and OCR, run concurrently."""
    if llm_settings.llm_provider != "groq":
        raise IngestionProviderError()

    with ThreadPoolExecutor(max_workers=2) as executor:
        vlm_future = executor.submit(_describe_image, image_bytes, filename)
        ocr_future = executor.submit(ocr_image, image_bytes)
        description = vlm_future.result()
        ocr_text = ocr_future.result()

    if ingest_settings.ingest_image_delay_ms > 0:
        time.sleep(ingest_settings.ingest_image_delay_ms / 1000.0)

    parts = [f"[VISUAL DESCRIPTION]\n{description}"]
    if ocr_text:
        parts.append(f"[TEXT IN IMAGE]\n{ocr_text}")
    return "\n\n".join(parts)


def describe_image(image_bytes: bytes, filename: str = "uploaded image") -> str:
    """Backward-compatible VLM-only helper used where OCR is not needed."""
    text = _describe_image(image_bytes, filename)
    if ingest_settings.ingest_image_delay_ms > 0:
        time.sleep(ingest_settings.ingest_image_delay_ms / 1000.0)
    return text


def extract_image(path: str, source_file: str) -> list[ExtractedBlock]:
    with open(path, "rb") as handle:
        image_bytes = handle.read()

    if not image_bytes:
        return []

    combined = process_image(image_bytes, source_file)
    return [
        ExtractedBlock(
            text=combined,
            chunk_type="image_derived",
            source_file=source_file,
        )
    ]


def is_image_extension(ext: str) -> bool:
    return ext in _IMAGE_EXTENSIONS
