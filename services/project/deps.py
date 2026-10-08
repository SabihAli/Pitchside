import hashlib
from typing import Annotated

from fastapi import Header

from futbot_common.errors import AuthError


def require_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise AuthError("LOGIN_REQUIRED", "Authentication required.", 403)
    return x_user_id


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
