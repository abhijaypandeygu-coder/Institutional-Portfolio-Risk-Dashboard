import os
import hashlib
import shutil
from typing import Tuple, Optional


class ArtifactStorageError(Exception):
    pass


class ReportArtifactStorageService:
    """Institutional-grade file storage abstraction for historical report artifacts.
    
    Guarantees:
    - Path traversal prevention.
    - Two-phase storage workflow (temp write -> hash verify -> atomic commit/move).
    - SHA-256 verification on ingestion and retrieval.
    - Storage key isolation: internal filesystem paths are never exposed to clients.
    """

    def __init__(self, base_storage_dir: str = "artifacts/reports"):
        self.base_storage_dir = base_storage_dir.replace("\\", "/")
        self.temp_storage_dir = os.path.join(self.base_storage_dir, "temp").replace("\\", "/")
        os.makedirs(self.base_storage_dir, exist_ok=True)
        os.makedirs(self.temp_storage_dir, exist_ok=True)

    def generate_storage_key(self, portfolio_id: str, archive_id: str, file_extension: str) -> str:
        """Construct deterministic, secure logical storage key: {portfolio_id}/{archive_id}.{ext}"""
        clean_ext = file_extension.lstrip(".")
        safe_portfolio = "".join(c for c in portfolio_id if c.isalnum() or c in ("-", "_"))
        safe_archive = "".join(c for c in archive_id if c.isalnum() or c in ("-", "_"))
        return f"{safe_portfolio}/{safe_archive}.{clean_ext}"

    def write_artifact_safe(
        self,
        storage_key: str,
        content_bytes: bytes,
        expected_hash: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """Writes artifact via temporary staging to prevent incomplete or corrupt persistence.
        
        Returns:
            Tuple of (storage_key, calculated_sha256_hash, file_size_bytes)
        """
        if ".." in storage_key or storage_key.startswith("/"):
            raise ArtifactStorageError("Invalid storage key: path traversal attempt detected.")

        calculated_hash = hashlib.sha256(content_bytes).hexdigest()
        if expected_hash and calculated_hash.lower() != expected_hash.lower():
            raise ArtifactStorageError(
                f"Integrity check failed during staging: expected {expected_hash}, calculated {calculated_hash}"
            )

        file_size = len(content_bytes)
        temp_filename = f"temp_{calculated_hash}_{os.getpid()}.tmp"
        temp_filepath = os.path.join(self.temp_storage_dir, temp_filename).replace("\\", "/")

        final_filepath = os.path.join(self.base_storage_dir, storage_key).replace("\\", "/")
        final_dir = os.path.dirname(final_filepath)
        os.makedirs(final_dir, exist_ok=True)

        try:
            with open(temp_filepath, "wb") as f:
                f.write(content_bytes)

            # Move atomically
            shutil.move(temp_filepath, final_filepath)
        except Exception as e:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except OSError:
                    pass
            raise ArtifactStorageError(f"Failed to persist report artifact: {str(e)}") from e

        return storage_key, calculated_hash, file_size

    def read_artifact(self, storage_key: str) -> bytes:
        """Retrieves raw binary bytes of stored report artifact."""
        if ".." in storage_key or storage_key.startswith("/"):
            raise ArtifactStorageError("Invalid storage key: path traversal attempt detected.")

        filepath = os.path.join(self.base_storage_dir, storage_key).replace("\\", "/")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Artifact not found for storage key: {storage_key}")

        with open(filepath, "rb") as f:
            return f.read()

    def verify_integrity(self, storage_key: str, expected_hash: str) -> Tuple[bool, Optional[str]]:
        """Verifies stored artifact on disk against its registered SHA-256 hash.
        
        Returns:
            Tuple of (is_valid, calculated_hash)
        """
        try:
            content = self.read_artifact(storage_key)
            actual_hash = hashlib.sha256(content).hexdigest()
            return (actual_hash.lower() == expected_hash.lower(), actual_hash)
        except FileNotFoundError:
            return (False, None)
        except Exception:
            return (False, None)

    def remove_artifact(self, storage_key: str) -> bool:
        """Deletes physical artifact file upon approved policy disposal."""
        if ".." in storage_key or storage_key.startswith("/"):
            raise ArtifactStorageError("Invalid storage key: path traversal attempt detected.")
        filepath = os.path.join(self.base_storage_dir, storage_key).replace("\\", "/")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
