#!/usr/bin/env python
"""
Institutional Deployment Launcher & Lifecycle CLI for M15.11.
Provides unified lifecycle control: validate, start, status, stop, and release management.
"""
import sys
import argparse
import subprocess
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.modules.infrastructure_platform.deployment.services import (
    EnvironmentValidator,
    ServiceOrchestrator,
    ReleaseManager,
)


def cmd_validate(args):
    """Executes preflight validation checks."""
    print("=" * 60)
    print("M15.11 Preflight Environment & Configuration Validation")
    print("=" * 60)
    res = EnvironmentValidator.validate_full_environment()
    print(f"Python Version:       {res['python_version']} (Compatible)")
    print(f"Node.js Version:      {res['node_version'] or 'Not installed / PATH optional'}")
    print(f"Database URL Safe:    {res['database_url_safe']}")
    print("Port Availability:")
    for port, free in res['port_availability'].items():
        state = "Available" if free else "Active / Bound"
        print(f"  - Port {port}:        {state}")

    if res['warnings']:
        print("\nWarnings:")
        for w in res['warnings']:
            print(f"  [!] {w}")

    print("-" * 60)
    if res['is_valid']:
        print("OVERALL RESULT: [PASSED] - Ready for deployment.")
        sys.exit(0)
    else:
        print("OVERALL RESULT: [FAILED] - Prerequisites not satisfied.")
        sys.exit(1)


def cmd_status(args):
    """Displays operational readiness of services and release state."""
    print("=" * 60)
    print("Institutional Portfolio Risk Dashboard - Deployment Status")
    print("=" * 60)
    overall = ServiceOrchestrator.get_overall_application_status()
    current_rel = ReleaseManager.get_current_release()
    print(f"Application Version:  {current_rel['application_version']} ({current_rel['build_identifier']})")
    print(f"Schema Revision:      {current_rel['schema_revision']}")
    print(f"Overall State:        [{overall.value}]")
    print("\nRegistered Services:")
    for s in ServiceOrchestrator.get_service_states():
        status_tag = f"[{s['status'].value}]"
        mand = "(Mandatory)" if s['is_mandatory'] else "(Optional)"
        print(f"  * {s['service_name']:<40} {status_tag:<12} {mand}")
        print(f"    Endpoint: {s['endpoint']}")


def cmd_manifest(args):
    """Prints machine-readable release manifest."""
    import json
    manifest = ReleaseManager.generate_release_manifest()
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Institutional Portfolio Risk Dashboard - Deployment Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    sub_val = subparsers.add_parser("validate", help="Validate runtime environment and configurations")
    sub_val.set_defaults(func=cmd_validate)

    # status
    sub_stat = subparsers.add_parser("status", help="Display service status and active release")
    sub_stat.set_defaults(func=cmd_status)

    # manifest
    sub_man = subparsers.add_parser("manifest", help="Generate machine-readable release manifest")
    sub_man.set_defaults(func=cmd_manifest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
