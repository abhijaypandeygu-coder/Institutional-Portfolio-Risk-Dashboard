"""
Testing Configuration and Environment Management Service.
Handles test profile loading, safe execution parameters, and test environment isolation.
"""
import os
import sys
import platform
from typing import Dict, Any, List
from backend.app.modules.infrastructure_platform.testing_infrastructure.models.testing_models import (
    TestProfileType,
)


class TestConfigService:
    """Manages testing profiles, environment isolation safeguards, and execution boundaries."""

    APPROVED_PROFILES: Dict[str, Dict[str, Any]] = {
        "unit": {
            "name": "Fast Unit Testing Suite",
            "type": TestProfileType.UNIT,
            "description": "Isolated mathematical correctness and business logic tests.",
            "command_args": ["-m", "not integration and not performance and not slow", "--maxfail=10"],
            "timeout_seconds": 60,
        },
        "integration": {
            "name": "System Integration Suite",
            "type": TestProfileType.INTEGRATION,
            "description": "Database, API contracts, and cross-module interactions.",
            "command_args": ["-m", "integration", "--maxfail=5"],
            "timeout_seconds": 120,
        },
        "regression": {
            "name": "Regression & Baseline Suite",
            "type": TestProfileType.REGRESSION,
            "description": "Mathematical reference comparisons against frozen baselines.",
            "command_args": ["backend/tests/regression", "--maxfail=5"],
            "timeout_seconds": 90,
        },
        "performance": {
            "name": "Benchmark & Performance Suite",
            "type": TestProfileType.PERFORMANCE,
            "description": "Latency, throughput, and numerical calculation benchmarks.",
            "command_args": ["backend/tests/performance", "--benchmark-columns=min,max,mean,stddev,median"],
            "timeout_seconds": 180,
        },
        "smoke": {
            "name": "Smoke Sanity Verification",
            "type": TestProfileType.SMOKE,
            "description": "Rapid verification of critical application endpoints.",
            "command_args": ["-m", "smoke"],
            "timeout_seconds": 30,
        },
        "full": {
            "name": "Complete Platform Test Suite",
            "type": TestProfileType.FULL,
            "description": "Runs complete testing suite across all modules.",
            "command_args": ["backend/tests"],
            "timeout_seconds": 300,
        },
    }

    @staticmethod
    def get_environment_metadata() -> Dict[str, Any]:
        """Gathers deterministic hardware and software environment details."""
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "processor": platform.processor(),
            "environment": os.getenv("APP_ENV", "testing"),
        }

    @staticmethod
    def validate_test_database_isolation(db_url: str) -> bool:
        """
        Safety gate: Ensures destructive test setups NEVER execute against production databases.
        """
        prohibited_keywords = ["prod", "production", "live_data"]
        lowered = db_url.lower()
        for kw in prohibited_keywords:
            if kw in lowered:
                return False
        return True

    @staticmethod
    def get_profile_config(profile_id: str) -> Dict[str, Any]:
        """Resolves configuration for an approved test profile."""
        if profile_id not in TestConfigService.APPROVED_PROFILES:
            raise ValueError(f"Unknown or unapproved test profile: {profile_id}")
        return TestConfigService.APPROVED_PROFILES[profile_id]
