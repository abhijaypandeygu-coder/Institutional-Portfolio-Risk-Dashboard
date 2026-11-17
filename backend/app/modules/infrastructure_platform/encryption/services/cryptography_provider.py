import os
import json
import base64
import secrets
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptographyProvider:
    """Institutional cryptographic provider implementing AES-256-GCM with AAD context binding."""

    NONCE_LENGTH = 12  # Standard 96-bit nonce for AES-GCM
    KEY_LENGTH = 32   # 256-bit key

    @classmethod
    def generate_key(cls) -> bytes:
        """Generates a cryptographically random 256-bit AES key."""
        return AESGCM.generate_key(bit_length=256)

    @classmethod
    def encrypt(
        cls,
        key: bytes,
        plaintext: str,
        aad_context: Optional[Dict[str, Any]] = None,
        key_id: Optional[str] = None,
    ) -> str:
        """Encrypts plaintext with AES-256-GCM, returning a structured Base64/JSON versioned envelope."""
        if len(key) != cls.KEY_LENGTH:
            raise ValueError(f"Invalid key length: expected {cls.KEY_LENGTH} bytes, got {len(key)}")

        nonce = secrets.token_bytes(cls.NONCE_LENGTH)
        aesgcm = AESGCM(key)

        aad_bytes = json.dumps(aad_context, sort_keys=True).encode("utf-8") if aad_context else None
        plaintext_bytes = plaintext.encode("utf-8")

        # AESGCM encrypt appends 16-byte authentication tag to ciphertext
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, aad_bytes)

        payload = {
            "v": 1,
            "alg": "AES-256-GCM",
            "kid": key_id or "default",
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "data": base64.b64encode(ciphertext_with_tag).decode("utf-8"),
            "aad": aad_context,
        }
        return json.dumps(payload)

    @classmethod
    def decrypt(
        cls,
        key: bytes,
        envelope_json: str,
        expected_aad_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Decrypts structured envelope and authenticates AAD and integrity tag."""
        if len(key) != cls.KEY_LENGTH:
            raise ValueError(f"Invalid key length: expected {cls.KEY_LENGTH} bytes, got {len(key)}")

        try:
            payload = json.loads(envelope_json)
        except Exception:
            raise ValueError("Malformed encrypted payload: invalid JSON envelope.")

        if payload.get("v") != 1 or payload.get("alg") != "AES-256-GCM":
            raise ValueError(f"Unsupported payload format or algorithm: {payload.get('alg')}")

        nonce = base64.b64decode(payload["nonce"])
        ciphertext_with_tag = base64.b64decode(payload["data"])

        # Validate AAD Context binding
        payload_aad = payload.get("aad")
        if expected_aad_context is not None:
            if payload_aad != expected_aad_context:
                raise ValueError("AAD verification failed: ciphertext is not bound to this execution context.")

        aad_bytes = json.dumps(payload_aad, sort_keys=True).encode("utf-8") if payload_aad else None
        aesgcm = AESGCM(key)

        try:
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, aad_bytes)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError("Decryption failed: invalid key, corrupted ciphertext, or altered authentication tag.")
