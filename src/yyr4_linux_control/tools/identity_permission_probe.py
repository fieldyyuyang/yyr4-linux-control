"""CLI tool for YYR4 identity and permission validation."""

import argparse
import json
import os
import sys
from pathlib import Path
from dataclasses import asdict

from yyr4_linux_control.integration.identity_permission_validation import (
    validate_identity_and_permissions,
    IdentityPermissionValidationResult,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YYR4 Identity and Permission Validation Probe"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Execute on real hardware using actual udev and filesystem permissions.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for the generated structured JSON report.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Format the JSON output with indentation.",
    )

    args = parser.parse_args()

    if not args.real:
        print("This tool requires --real to access hardware.", file=sys.stderr)
        return 8  # RUNTIME_OR_DEPENDENCY_FAILURE

    if not args.output:
        print("Output path is required when running with --real.", file=sys.stderr)
        return 8

    try:
        from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
        from yyr4_linux_control.integration.preflight import FilesystemIdentityPermissionChecker
        from yyr4_linux_control.integration.preflight import check_runtime_preflight

        preflight = check_runtime_preflight()
        if not preflight.ready_for_discovery:
            print("Preflight checks failed:", file=sys.stderr)
            for blocker in preflight.blockers:
                print(f"- {blocker}", file=sys.stderr)
            return 8

        backend = LinuxUdevDiscoveryBackend()
        checker = FilesystemIdentityPermissionChecker()

    except ImportError as e:
        print(f"Missing required dependency: {e}", file=sys.stderr)
        return 8
    except Exception as e:
        print(f"Failed to construct real dependencies: {e}", file=sys.stderr)
        return 8

    result = validate_identity_and_permissions(
        discovery_backend=backend,
        permission_checker=checker,
    )

    # Atomic write
    output_path = Path(args.output)
    temp_path = output_path.with_suffix(".json.tmp")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            if args.pretty:
                json.dump(asdict(result), f, indent=2)
            else:
                json.dump(asdict(result), f)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, output_path)
    except Exception as e:
        print(f"Failed to write result to {args.output}: {e}", file=sys.stderr)
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        return 12  # RESULT_WRITE_FAILURE

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
