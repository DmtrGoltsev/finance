"""Validate the entire host inventory before any line is logged or uploaded."""

from __future__ import annotations

import sys
import re
from pathlib import Path

YES_NO = frozenset({"yes", "no"})
YES_NO_UNKNOWN = frozenset({"yes", "no", "unknown"})
SERVICE_STATES = frozenset(
    {"active", "inactive", "failed", "activating", "deactivating", "not_found", "unknown"}
)

FIELDS: dict[str, frozenset[str]] = {
    "schema": frozenset({"finance_inventory_v5"}),
    "hostname_sha256": frozenset({"unknown"}),
    "os_id": frozenset({"unknown"}),
    "os_version": frozenset({"unknown"}),
    "os_arch": frozenset({"x86_64", "aarch64", "armv7l", "i686", "unknown"}),
    "package_manager": frozenset({"apt-get", "dnf", "yum", "apk", "none"}),
    "docker_candidate": frozenset({"usr_bin", "usr_local_bin", "snap_bin", "none"}),
    "node_available": YES_NO,
    "node_version": frozenset({"unknown"}),
    "npm_available": YES_NO,
    "npm_version": frozenset({"unknown"}),
    "apt_cached_node22_available": YES_NO_UNKNOWN,
    "apt_cached_node24_available": YES_NO_UNKNOWN,
    "mem_total_kib": frozenset({"unknown"}),
    "mem_available_kib": frozenset({"unknown"}),
    "mem_available_bytes": frozenset({"unknown"}),
    "swap_total_bytes": frozenset({"unknown"}),
    "swap_free_bytes": frozenset({"unknown"}),
    "swapon_active": YES_NO_UNKNOWN,
    "swapon_total_bytes": frozenset({"unknown"}),
    "opt_mount_target": frozenset({"/", "/opt", "/var", "/var/lib", "/var/lib/postgresql", "other", "unknown"}),
    "postgres_mount_target": frozenset({"/", "/opt", "/var", "/var/lib", "/var/lib/postgresql", "other", "unknown"}),
    "opt_mount_fstype": frozenset({"ext4", "xfs", "btrfs", "zfs", "overlay", "tmpfs", "other", "unknown"}),
    "postgres_mount_fstype": frozenset({"ext4", "xfs", "btrfs", "zfs", "overlay", "tmpfs", "other", "unknown"}),
    "opt_postgres_same_device": YES_NO_UNKNOWN,
    "finance_current_release_bytes": frozenset({"unknown"}),
    "finance_releases_total_bytes": frozenset({"unknown"}),
    "finance_prior_releases_bytes": frozenset({"unknown"}),
    "finance_backup_bytes": frozenset({"unknown"}),
    "postgres_data_bytes": frozenset({"unknown"}),
    "postgres_wal_bytes": frozenset({"unknown"}),
    "opt_free_kib": frozenset({"unknown"}),
    "var_lib_free_kib": frozenset({"unknown"}),
    "ssh_user": frozenset({"unknown"}),
    "docker_group_member": YES_NO_UNKNOWN,
    "systemctl_available": YES_NO,
    "backend_service_active": YES_NO,
    "backend_service_user": frozenset({"default", "unknown"}),
    "backend_service_group": frozenset({"default", "unknown"}),
    "backend_unit_path": frozenset({
        "/etc/systemd/system/finance-backend.service",
        "/lib/systemd/system/finance-backend.service",
        "/usr/lib/systemd/system/finance-backend.service",
        "other", "unknown",
    }),
    "backend_working_directory": frozenset({"unset", "other", "unknown"}),
    "docker_service_state": SERVICE_STATES,
    "n8n_service_state": SERVICE_STATES,
    "nginx_service_state": SERVICE_STATES,
    "caddy_service_state": SERVICE_STATES,
    "postgresql_service_state": SERVICE_STATES,
    "finance_backend_service_state": SERVICE_STATES,
    "finance_backend_main_rss_kib": frozenset({"unknown"}),
    "finance_backend_main_cpu_percent": frozenset({"unknown"}),
    "postgresql_main_rss_kib": frozenset({"unknown"}),
    "postgresql_main_cpu_percent": frozenset({"unknown"}),
    "nginx_main_rss_kib": frozenset({"unknown"}),
    "nginx_main_cpu_percent": frozenset({"unknown"}),
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
    "backend_env_deepseek_name_present": YES_NO_UNKNOWN,
    "backend_env_fcm_name_present": YES_NO_UNKNOWN,
    "backend_env_delivery_hmac_name_present": YES_NO_UNKNOWN,
    "pg_dump_version": frozenset({"unknown"}),
    "alembic_current": frozenset({"unknown"}),
    "outbox_table_present": YES_NO_UNKNOWN,
    "finance_db_size_bytes": frozenset({"unknown"}),
    "postgres_max_connections": frozenset({"unknown"}),
    "backend_loopback_health": YES_NO,
    "n8n_loopback_health": YES_NO,
    "backend_8081_http_status": frozenset({"000"}),
    "n8n_5678_http_status": frozenset({"000"}),
    "backend_8081_loopback_listener": YES_NO_UNKNOWN,
    "listener_5680": frozenset({"none", "loopback", "non_loopback", "unknown"}),
    "listener_8000": frozenset({"none", "loopback", "non_loopback", "unknown"}),
    "container_to_backend_reachability": frozenset({"unknown"}),
    "docker_cli_available": YES_NO,
    "docker_socket_exists": YES_NO,
    "docker_socket_writable": YES_NO,
    "docker_socket_group": frozenset({"default", "unknown"}),
    "sudo_n_list_available": YES_NO_UNKNOWN,
    "sudo_n_docker_listed": YES_NO_UNKNOWN,
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

for name in (
    "n8n_stack_root_exists",
    "n8n_stack_current_exists",
    "n8n_stack_current_symlink",
    "backend_current_exists",
    "backend_current_symlink",
):
    FIELDS[name] = YES_NO

for name in ("backend", "n8n", "gateway", "worker"):
    FIELDS[f"backend_network_{name}_attached"] = YES_NO_UNKNOWN

for name in ("opt", "postgres", "backup"):
    for suffix in ("total_bytes", "used_bytes", "available_bytes", "total_inodes", "used_inodes", "available_inodes"):
        FIELDS[f"{name}_{suffix}"] = frozenset({"unknown"})

DYNAMIC_PATTERNS = {
    "hostname_sha256": r"[0-9a-f]{64}",
    "os_id": r"[a-z][a-z0-9._-]{0,31}",
    "os_version": r"[0-9][A-Za-z0-9._-]{0,31}",
    "ssh_user": r"[a-z_][a-z0-9_-]{0,31}",
    "backend_service_user": r"[a-z_][a-z0-9_-]{0,31}",
    "backend_service_group": r"[a-z_][a-z0-9_-]{0,31}",
    "docker_socket_group": r"[a-z_][a-z0-9_-]{0,31}",
    "backend_working_directory": r"/opt/finance(/[A-Za-z0-9._-]+)*",
    "pg_dump_version": r"[0-9]+(\.[0-9]+){0,2}",
    "node_version": r"[0-9]+(\.[0-9]+){1,2}",
    "npm_version": r"[0-9]+(\.[0-9]+){1,2}",
    "alembic_current": r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    "backend_8081_http_status": r"[1-5][0-9]{2}",
    "n8n_5678_http_status": r"[1-5][0-9]{2}",
}
for name in ("mem_total_kib", "mem_available_kib", "opt_free_kib", "var_lib_free_kib"):
    DYNAMIC_PATTERNS[name] = r"[0-9]{1,20}"
for name in (
    "mem_available_bytes", "swap_total_bytes", "swap_free_bytes", "swapon_total_bytes",
    "finance_current_release_bytes", "finance_releases_total_bytes", "finance_prior_releases_bytes",
    "finance_backup_bytes", "postgres_data_bytes", "postgres_wal_bytes",
    "finance_db_size_bytes", "postgres_max_connections",
):
    DYNAMIC_PATTERNS[name] = r"[0-9]{1,20}"
for name in ("opt", "postgres", "backup"):
    for suffix in ("total_bytes", "used_bytes", "available_bytes", "total_inodes", "used_inodes", "available_inodes"):
        DYNAMIC_PATTERNS[f"{name}_{suffix}"] = r"[0-9]{1,20}"
for name in ("finance_backend", "postgresql", "nginx"):
    DYNAMIC_PATTERNS[f"{name}_main_rss_kib"] = r"[0-9]{1,20}"
    DYNAMIC_PATTERNS[f"{name}_main_cpu_percent"] = r"[0-9]{1,5}(\.[0-9]+)?"


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
        dynamic_valid = key in DYNAMIC_PATTERNS and re.fullmatch(DYNAMIC_PATTERNS[key], value)
        if key in result or key not in FIELDS or (value not in FIELDS[key] and not dynamic_valid):
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
