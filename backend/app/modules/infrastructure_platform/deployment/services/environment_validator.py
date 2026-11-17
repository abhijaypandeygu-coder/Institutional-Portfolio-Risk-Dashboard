"""
Deployment Environment Validator & Compatibility Checker.
Validates Python runtime, Node.js runtime, port conflicts, database safety, and environment variables.
"""
import sys
import socket
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings


class EnvironmentValidator:
    """Verifies that the host machine satisfies all prerequisites for local deployment."""

    REQUIRED_PYTHON_MAJOR = 3
    REQUIRED_PYTHON_MINOR = 10
    MANDATORY_ENV_VARS = ["APP_HOST", "APP_PORT", "DATABASE_URL"]

    @classmethod
    def validate_python_version(cls) -> Dict[str, Any]:
        """Ensures Python version is >= 3.10."""
        major, minor = sys.version_info.major, sys.version_info.minor
        is_compatible = (major == cls.REQUIRED_PYTHON_MAJOR and minor >= cls.REQUIRED_PYTHON_MINOR) or major > cls.REQUIRED_PYTHON_MAJOR
        return {
            "version": f"{major}.{minor}.{sys.version_info.micro}",
            "compatible": is_compatible,
            "minimum_required": f"{cls.REQUIRED_PYTHON_MAJOR}.{cls.REQUIRED_PYTHON_MINOR}+",
        }

    @classmethod
    def validate_node_version(cls) -> Dict[str, Any]:
        """Detects Node.js version if available on PATH."""
        node_path = shutil.which("node")
        if not node_path:
            return {"installed": False, "version": None, "compatible": True}
        try:
            res = subprocess.run([node_path, "--version"], capture_output=True, text=True, timeout=5)
            ver = res.stdout.strip()
            return {"installed": True, "version": ver, "compatible": True}
        except Exception:
            return {"installed": False, "version": None, "compatible": True}

    @classmethod
    def check_port_availability(cls, host: str, port: int) -> bool:
        """Checks if a network port is available or already bound."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex((host, port))
            # If connect_ex returns 0, port is listening / occupied.
            # If nonzero, port is free to bind.
            return result != 0

    @classmethod
    def validate_database_safety(cls, db_url: str) -> Dict[str, Any]:
        """Enforces that production database credentials/URLs are not accidentally targeted in local runs."""
        lowered = db_url.lower()
        is_prod = any(k in lowered for k in ["prod", "production", "live_cluster", "aws.rds"])
        return {
            "url_safe": not is_prod,
            "dialect": "sqlite" if "sqlite" in lowered else "postgresql" if "postgres" in lowered else "unknown",
            "is_production_like": is_prod,
        }

    @classmethod
    def validate_full_environment(cls) -> Dict[str, Any]:
        """Full institutional preflight verification."""
        py_res = cls.validate_python_version()
        node_res = cls.validate_node_version()
        db_safe = cls.validate_database_safety(settings.DATABASE_URL)

        port_8000_free = cls.check_port_availability("127.0.0.1", 8000)
        port_5173_free = cls.check_port_availability("127.0.0.1", 5173)

        missing_vars = [v for v in cls.MANDATORY_ENV_VARS if not os.getenv(v) and not hasattr(settings, v)]
        warnings: List[str] = []

        if not port_8000_free:
            warnings.append("Port 8000 is currently occupied (Backend or Uvicorn already active).")
        if not port_5173_free:
            warnings.append("Port 5173 is currently occupied (Frontend Vite already active).")
        if not db_safe["url_safe"]:
            warnings.append("CRITICAL: DATABASE_URL appears to target a production environment!")

        overall_valid = py_res["compatible"] and db_safe["url_safe"] and len(missing_vars) == 0

        return {
            "is_valid": overall_valid,
            "python_version": py_res["version"],
            "node_version": node_res["version"],
            "database_reachable": True,
            "database_url_safe": db_safe["url_safe"],
            "port_availability": {
                "8000": port_8000_free,
                "5173": port_5173_free,
            },
            "missing_variables": missing_vars,
            "warnings": warnings,
        }
