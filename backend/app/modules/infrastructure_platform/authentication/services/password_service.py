import hashlib
import os
import secrets
from typing import Tuple


class PasswordSecurityService:
    """Institutional password hashing using Python hashlib.scrypt with cryptographically random salts."""

    # Default scrypt parameters: N=2^14 (16384), r=8, p=1, maxmem=32MB
    N = 16384
    r = 8
    p = 1
    KEY_LEN = 64

    @classmethod
    def hash_password(cls, password: str, salt: str = None) -> Tuple[str, str]:
        """Hashes password with scrypt and returns (hex_digest, salt)."""
        if not salt:
            salt = secrets.token_hex(16)
        salt_bytes = salt.encode("utf-8")
        password_bytes = password.encode("utf-8")

        key = hashlib.scrypt(
            password_bytes,
            salt=salt_bytes,
            n=cls.N,
            r=cls.r,
            p=cls.p,
            maxmem=32 * 1024 * 1024,
            dklen=cls.KEY_LEN,
        )
        return key.hex(), salt

    @classmethod
    def verify_password(cls, password: str, expected_hash: str, salt: str) -> bool:
        """Constant-time verification of submitted password against expected hash."""
        computed_hash, _ = cls.hash_password(password, salt=salt)
        return secrets.compare_digest(computed_hash.lower(), expected_hash.lower())
