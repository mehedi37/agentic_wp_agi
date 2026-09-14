import uuid

import pytest

from app.core.security import (
    JWTError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip() -> None:
    hashed = hash_password("demo1234")
    assert hashed != "demo1234"
    assert verify_password("demo1234", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "manager")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "manager"


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(JWTError):
        decode_access_token("not-a-valid-token")
