
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from supermart.config import settings
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from supermart.api.dependencies import get_current_user
from supermart.models import Base, User
from supermart.security.tokens import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            session.add_all([
                User(
                    user_id=1,
                    username="active_test",
                    password_hash="test-hash",
                    role="store_owner",
                    is_active=True,
                    must_reset_password=False,
                ),
                User(
                    user_id=2,
                    username="inactive_test",
                    password_hash="test-hash",
                    role="store_owner",
                    is_active=False,
                    must_reset_password=False,
                ),
                User(
                    user_id=3,
                    username="reset_test",
                    password_hash="test-hash",
                    role="supplier",
                    is_active=True,
                    must_reset_password=True,
                ),
            ])
            session.commit()
            yield session
    finally:
        engine.dispose()


def bearer(token: str):
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def test_token_round_trip():
    token = create_access_token(1)
    claims = decode_access_token(token)

    assert claims["sub"] == "1"


def test_expired_token_is_rejected():
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(ValueError):
        decode_access_token(token)

def test_missing_credentials_are_rejected(db):
    with pytest.raises(HTTPException) as exc:
        get_current_user(None, db)

    assert exc.value.status_code == 401


def test_valid_token_returns_active_user(db):
    token = create_access_token(1)

    user = get_current_user(bearer(token), db)

    assert user.user_id == 1
    assert user.username == "active_test"


def test_nonexistent_user_is_rejected(db):
    token = create_access_token(999)

    with pytest.raises(HTTPException) as exc:
        get_current_user(bearer(token), db)

    assert exc.value.status_code == 401


def test_inactive_user_is_rejected(db):
    token = create_access_token(2)

    with pytest.raises(HTTPException) as exc:
        get_current_user(bearer(token), db)

    assert exc.value.status_code == 403


def test_password_reset_required_user_is_rejected(db):
    token = create_access_token(3)

    with pytest.raises(HTTPException) as exc:
        get_current_user(bearer(token), db)

    assert exc.value.status_code == 403
