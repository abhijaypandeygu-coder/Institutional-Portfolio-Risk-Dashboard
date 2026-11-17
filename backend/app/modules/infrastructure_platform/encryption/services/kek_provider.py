import os
import hashlib
import base64
from typing import Optional


class MasterKekProvider:
    """Manages Key Encryption Key (KEK) resolution from protected environment variables.
    Separates master key hierarchy from database persistence.
    """

    KEK_ENV_VAR = "INSTITUTIONAL_MASTER_KEK"
    DEFAULT_DEV_SALT = b"Antigravity_Institutional_KEK_2026_Salt"

    @classmethod
    def get_master_kek(cls) -> bytes:
        """Retrieves or derives the 256-bit Master Key Encryption Key."""
        raw_key = os.getenv(cls.KEK_ENV_VAR)
        if raw_key:
            # If provided as hex or base64
            try:
                decoded = base64.b64decode(raw_key)
                if len(decoded) == 32:
                    return decoded
            except Exception:
                pass
            return hashlib.scrypt(
                raw_key.encode("utf-8"),
                salt=cls.DEFAULT_DEV_SALT,
                n=16384,
                r=8,
                p=1,
                dklen=32,
            )

        # Standard deterministic local development fallback
        return hashlib.scrypt(
            b"LOCAL_DEFAULT_MASTER_KEY_ENCRYPTION_KEY_2026",
            salt=cls.DEFAULT_DEV_SALT,
            n=16384,
            r=8,
            p=1,
            dklen=32,
        )
