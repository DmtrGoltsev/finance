"""Validate the entire host inventory before any line is logged or uploaded."""

from __future__ import annotations

import sys
from pathlib import Path

YES_NO = frozenset({"yes", "no"})
YES_NO_UNKNOWN = frozenset({"yes", "no", "unknown"})

FIELDS: dict[str, frozenset[str]] = {
    "schema": frozenset({"finance_inventory_v2"}),
    "systemctl_available": YES_NO,
    "backend_service_active": YES_NO,
    "finance_delivery_unit_present": YES_NO,
    "finance_n8n_unit_present": YES_NO,
    "finance_gateway_unit_present": YES_NO,
    "backend_service_wiring": frozenset({"unknown"}),
    "backend_current_scope": frozenset(
        {"not_symlink", "within_releases", "outside_releases"}
    ),
    "frontend_current_scope": frozenset(
        {"not_symlink", "within_releases", "outside_releases"}
    ),
    "backend_env_exists": YES_NO,
    "backend_env_readable": YES_NO,
    "provider_credential_presence": frozenset({"unknown"}),
    "backend_loopback_health": YES_NO,
    "n8n_loopback_health": YES_NO,
    "backend_8081_loopback_listener": YES_NO_UNKNOWN,
    "container_to_backend_reachability": frozenset({"unknown"}),
    "docker_cli_available": YES_NO,
    "docker_daemon_accessible": YES_NO,
    "compose_available": YES_NO_UNKNOWN,
    "backend_network_exists": YES_NO_UNKNOWN,
    "backend_network_internal": YES_NO_UNKNOWN,
    "n8n_container_exists": YES_NO_UNKNOWN,
    "gateway_container_exists": YES_NO_UNKNOWN,
    "worker_container_exists": YES_NO_UNKNOWN,
    "n8n_volume_exists": YES_NO_UNKNOWN,
}

for name in (
    "backend_releases",
    "frontend_releases",
    "db_backup",
    "finance_etc",
    "n8n_candidate",
    "worker_candidate",
):
    for suffix in ("exists", "readable", "writable"):
        FIELDS[f"{name}_{suffix}"] = YES_NO

for name in ("backend", "n8n", "gateway", "worker"):
    FIELDS[f"backend_network_{name}_attached"] = YES_NO_UNKNOWN


def parse_inventory(data: bytes) -> dict[str, str]:
    if not data or len(data) > 16_384 or b"\r" in data or not data.endswith(b"\n"):
        raise ValueError("invalid inventory evidence")
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("invalid inventory evidence") from exc
    result: dict[str, str] = {}
    for line in lines:
        if line.count("=") != 1:
            raise ValueError("invalid inventory evidence")
        key, value = line.split("=", 1)
        if key in result or key not in FIELDS or value not in FIELDS[key]:
            raise ValueError("invalid inventory evidence")
        result[key] = value
    if result.keys() != FIELDS.keys():
        raise ValueError("invalid inventory evidence")
    return result


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("invalid inventory evidence")
        parse_inventory(Path(sys.argv[1]).read_bytes())
    except (OSError, ValueError):
        print("::error::Invalid inventory evidence; no host output published.", file=sys.stderr)
        raise SystemExit(1) from None
