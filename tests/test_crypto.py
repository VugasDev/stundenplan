import pytest
from cryptography.fernet import Fernet, InvalidToken
from app.crypto import CredentialCipher


def test_roundtrip_encrypt_decrypt():
    cipher = CredentialCipher(Fernet.generate_key())
    token = cipher.encrypt("geheim123")
    assert token != "geheim123"
    assert cipher.decrypt(token) == "geheim123"


def test_token_is_str():
    cipher = CredentialCipher(Fernet.generate_key())
    assert isinstance(cipher.encrypt("x"), str)


def test_wrong_key_cannot_decrypt():
    token = CredentialCipher(Fernet.generate_key()).encrypt("x")
    other = CredentialCipher(Fernet.generate_key())
    with pytest.raises(InvalidToken):
        other.decrypt(token)
