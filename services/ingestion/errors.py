class IngestionError(Exception):
    """Base class for ingestion failures."""


class UnsupportedFormatError(IngestionError):
    def __init__(self, filename: str, extension: str, accepted: list[str]):
        self.filename = filename
        self.extension = extension
        self.accepted = accepted
        super().__init__(
            f"Unsupported file type '{extension}'. "
            f"Accepted: {', '.join(accepted)}"
        )


class EmptyFileError(IngestionError):
    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"The uploaded file is empty: {filename}")


class FootballRelevanceError(IngestionError):
    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(
            "The uploaded file does not appear to contain football-related content "
            "and cannot be added to the knowledge base."
        )


class IngestionProviderError(IngestionError):
    def __init__(self):
        super().__init__(
            "File ingestion requires LLM_PROVIDER=groq. "
            "Set LLM_PROVIDER=groq and GROQ_API_KEY in your environment."
        )


class VisionUnavailableError(IngestionError):
    """Raised when the vision model call itself failed (rate limit, outage,
    etc.), as opposed to the model successfully describing non-football
    content. Keeping this distinct from FootballRelevanceError matters: an
    infra failure must never be laundered through the relevance classifier
    and reported to the user as "not football-related"."""

    def __init__(self, filename: str, detail: str):
        self.filename = filename
        super().__init__(
            f"Couldn't analyze the image in '{filename}' -- the vision model "
            f"is temporarily unavailable ({detail}). Please try uploading again "
            "in a moment."
        )


class DuplicateUploadError(IngestionError):
    def __init__(self, filename: str, existing_ingestion_id: int, existing_filename: str):
        self.filename = filename
        self.existing_ingestion_id = existing_ingestion_id
        self.existing_filename = existing_filename
        super().__init__(
            f"This file has already been uploaded as '{existing_filename}' "
            f"(ingestion #{existing_ingestion_id}). Duplicate uploads are not allowed."
        )
