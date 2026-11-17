import os
import hashlib
from typing import Tuple

class LocalStorageAdapter:
    """Handles persistent filesystem storage for generated export artifacts with SHA-256 hashes."""

    def __init__(self, base_storage_dir: str = "artifacts/exports"):
        self.base_storage_dir = base_storage_dir
        os.makedirs(self.base_storage_dir, exist_ok=True)

    def store_artifact(self, relative_filename: str, content_bytes: bytes) -> Tuple[str, str, int]:
        """Store binary artifact bytes and return (storage_reference, sha256_hash, file_size_bytes)."""
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        file_size = len(content_bytes)

        full_path = os.path.join(self.base_storage_dir, relative_filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(content_bytes)

        return full_path.replace("\\", "/"), file_hash, file_size

    def read_artifact(self, storage_reference: str) -> bytes:
        """Read bytes for an existing stored artifact."""
        if not os.path.exists(storage_reference):
            raise FileNotFoundError(f"Artifact not found at storage reference: {storage_reference}")
        with open(storage_reference, "rb") as f:
            return f.read()

    def verify_artifact_integrity(self, storage_reference: str, expected_hash: str) -> bool:
        """Verify stored file matches expected SHA-256 hash."""
        if not os.path.exists(storage_reference):
            return False
        content = self.read_artifact(storage_reference)
        actual_hash = hashlib.sha256(content).hexdigest()
        return actual_hash == expected_hash
