"""
Safe Test Execution Orchestrator for M15.10.
Executes approved pytest profiles through controlled subprocess execution,
preventing command injection and capturing stdout/stderr safely.
"""
import asyncio
import sys
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.modules.infrastructure_platform.testing_infrastructure.services.test_config_service import (
    TestConfigService,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.models.testing_models import (
    TestRunStatus,
)


class TestExecutionService:
    """Orchestrates test executions asynchronously with timeout and output capture."""

    # In-memory execution store for local tracking
    ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def execute_profile(
        cls,
        profile_id: str,
        module_target: Optional[str] = None,
        triggered_by: str = "tester",
    ) -> Dict[str, Any]:
        """
        Executes a registered test profile safely via sys.executable and pytest.
        """
        config = TestConfigService.get_profile_config(profile_id)
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        env_meta = TestConfigService.get_environment_metadata()

        record = {
            "run_id": run_id,
            "profile_id": profile_id,
            "status": TestRunStatus.RUNNING,
            "code_revision": "HEAD",
            "environment_metadata": env_meta,
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "duration_ms": None,
            "triggered_by": triggered_by,
            "passed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "error_summary": None,
            "artifact_reference": f"artifacts/test_runs/{run_id}.log",
            "output": "",
        }
        cls.ACTIVE_RUNS[run_id] = record

        # Build command safely without shell expansion
        cmd = [sys.executable, "-m", "pytest"]
        cmd.extend(config["command_args"])

        if module_target and module_target != "all":
            cmd.append(f"backend/tests/modules/{module_target}")

        t0 = time.perf_counter()
        timeout = config.get("timeout_seconds", 120)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd(),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            t1 = time.perf_counter()
            duration_ms = (t1 - t0) * 1000.0

            out_text = stdout.decode("utf-8", errors="replace")
            err_text = stderr.decode("utf-8", errors="replace")
            combined_output = f"{out_text}\n{err_text}".strip()

            # Parse simple pytest outcomes
            passed = 0
            failed = 0
            skipped = 0

            for line in combined_output.split("\n"):
                if "passed" in line or "failed" in line:
                    parts = line.strip("=").strip().split(",")
                    for p in parts:
                        p_str = p.strip()
                        if "passed" in p_str:
                            try:
                                passed = int(p_str.split()[0])
                            except Exception:
                                pass
                        elif "failed" in p_str:
                            try:
                                failed = int(p_str.split()[0])
                            except Exception:
                                pass
                        elif "skipped" in p_str:
                            try:
                                skipped = int(p_str.split()[0])
                            except Exception:
                                pass

            # Update run record
            record["completed_at"] = datetime.now(timezone.utc)
            record["duration_ms"] = round(duration_ms, 2)
            record["passed_count"] = passed
            record["failed_count"] = failed
            record["skipped_count"] = skipped
            record["output"] = combined_output[:10000] # bounded output

            if process.returncode == 0:
                record["status"] = TestRunStatus.PASSED
            else:
                record["status"] = TestRunStatus.FAILED if failed > 0 else TestRunStatus.ERROR
                record["error_summary"] = f"Pytest exited with code {process.returncode}"

        except asyncio.TimeoutError:
            record["completed_at"] = datetime.now(timezone.utc)
            record["status"] = TestRunStatus.ERROR
            record["error_summary"] = f"Execution timed out after {timeout} seconds"
        except Exception as ex:
            record["completed_at"] = datetime.now(timezone.utc)
            record["status"] = TestRunStatus.ERROR
            record["error_summary"] = str(ex)

        return record

    @classmethod
    def get_run(cls, run_id: str) -> Optional[Dict[str, Any]]:
        return cls.ACTIVE_RUNS.get(run_id)

    @classmethod
    def list_runs(cls) -> List[Dict[str, Any]]:
        return list(cls.ACTIVE_RUNS.values())
