from datetime import timedelta

from core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_does_not_return_plaintext() -> None:
    hashed = hash_password("hunter2")

    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("hunter2")

    assert not verify_password("wrong-password", hashed)


def test_hash_password_is_salted() -> None:
    # Same input should still produce different hashes (random salt per call).
    assert hash_password("hunter2") != hash_password("hunter2")


def test_access_token_roundtrip() -> None:
    token = create_access_token(subject="42")

    assert decode_access_token(token) == "42"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(subject="42", expires_delta=timedelta(minutes=-1))

    assert decode_access_token(token) is None


def test_malformed_token_is_rejected() -> None:
    assert decode_access_token("not-a-real-token") is None
