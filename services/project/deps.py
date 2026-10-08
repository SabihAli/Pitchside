import hashlib
from typing import Annotated

from fastapi import Header

from futbot_common.errors import AuthError
from services.project.config import settings


def require_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise AuthError("LOGIN_REQUIRED", "Authentication required.", 403)
    return x_user_id


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_uploads_enabled() -> None:
    if not settings.knowledge_uploads_enabled:
        raise AuthError(
            "KNOWLEDGE_READ_ONLY",
            "Adding files to the knowledge base is disabled.",
            403,
        )
