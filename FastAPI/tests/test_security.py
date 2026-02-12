from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_id,
    generate_temp_password,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify_roundtrip():
    plain = "StrongPass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    subject = "user-123"
    token = create_access_token(subject)
    decoded = decode_access_token(token)
    assert decoded == subject


def test_decode_invalid_token_and_generators():
    assert decode_access_token("not-a-jwt") is None
    assert len(generate_id()) > 10
    tmp = generate_temp_password(16)
    assert len(tmp) == 16
