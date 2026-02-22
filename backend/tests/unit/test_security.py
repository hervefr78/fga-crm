# =============================================================================
# FGA CRM - Tests unitaires des fonctions de securite
# =============================================================================


from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests du hachage bcrypt."""

    def test_hash_and_verify(self):
        password = "MonMotDePasse123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("incorrect", hashed) is False

    def test_hash_is_not_plaintext(self):
        password = "secret"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$2b$")

    def test_different_hashes_same_password(self):
        """Deux hash du meme mdp doivent etre differents (salt unique)."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJWT:
    """Tests des tokens JWT."""

    def test_access_token_roundtrip(self):
        data = {"sub": "user-123"}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        data = {"sub": "user-456"}
        token = create_refresh_token(data)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        result = decode_token("not.a.valid.token")
        assert result is None

    def test_decode_empty_string(self):
        result = decode_token("")
        assert result is None

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "test"})
        payload = decode_token(token)
        assert "exp" in payload
