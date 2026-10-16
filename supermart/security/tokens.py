
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from supermart.config import settings


ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access token for a user."""

    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id <= 0
    ):
        raise ValueError("user_id must be a positive integer")

    now = datetime.now(timezone.utc)
    lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(hours=settings.session_hours)
    )

    if lifetime.total_seconds() <= 0:
        raise ValueError("Token lifetime must be positive")

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + lifetime,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Validate a token's signature, expiry and required claims."""

    if not isinstance(token, str) or not token:
        raise ValueError("Invalid or expired access token")

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token") from exc

    subject = claims.get("sub")

    if (
        not isinstance(subject, str)
        or not subject.isascii()
        or not subject.isdigit()
        or int(subject) <= 0
    ):
        raise ValueError("Invalid token subject")

    return claims
