from cryptography.fernet import Fernet


class CredentialCipher:
    """Symmetrische Ver-/Entschlüsselung für WebUntis-Passwörter."""

    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")


def build_cipher(app) -> CredentialCipher:
    key = app.config["FERNET_KEY"]
    if not key:
        raise RuntimeError("FERNET_KEY ist nicht gesetzt.")
    return CredentialCipher(key)
