"""Read-only, fail-closed host-native Finance delivery approval contract."""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import urllib.request
from pathlib import Path

try:
    import pwd
except ImportError:  # Synthetic dry-run also runs on Windows.
    pwd = None


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


APPROVAL_FIELDS = {
    "mode", "inventory_run_id", "captured_at_utc", "approved_at_utc", "approval_ticket",
    "measurement_proof", "backup_restore_proof", "rollback_proof", "host_name",
    "os_id", "os_version_id", "architecture", "node_path", "node_version",
    "node_sha256", "npm_path", "npm_version", "npm_sha256", "n8n_lock_sha256",
    "gateway_lock_sha256", "postgres_version_num", "finance_database",
    "backend_current_revision", "backend_target_revision", "ports", "capacity",
}
CAPACITY_FIELDS = {
    "n8n_peak_kib", "gateway_peak_kib", "worker_peak_kib", "memory_reserve_kib",
    "install_kib", "database_growth_kib", "backup_kib", "restore_kib", "disk_reserve_kib",
}
PORTS = {"n8n": 5680, "gateway": 8080, "worker": 8091, "backend": 8081}
UNITS = {
    "n8n": "finance-investment-n8n.service",
    "gateway": "finance-investment-gateway.service",
    "worker": "finance-investment-worker.service",
}
MARKER = "# Managed by Finance host-native investment delivery.\n"


def _timestamp(value: str) -> dt.datetime:
    require(isinstance(value, str), "approval timestamp must be a string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("approval timestamp is invalid") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0), "approval timestamp must be UTC")
    return parsed


def validate_approval(raw: bytes, now: dt.datetime | None = None) -> dict:
    try:
        approval = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractError("host-native approval is not UTF-8 JSON") from exc
    require(type(approval) is dict and set(approval) == APPROVAL_FIELDS,
            "host-native approval fields are missing or unexpected")
    require(approval["mode"] == "host-native-v1", "Docker approval cannot authorize host-native delivery")
    now = now or dt.datetime.now(dt.timezone.utc)
    captured = _timestamp(approval["captured_at_utc"])
    approved = _timestamp(approval["approved_at_utc"])
    require(dt.timedelta(0) <= now - captured <= dt.timedelta(hours=24), "host inventory is missing or stale")
    require(captured <= approved <= now, "approval must follow inventory")
    require(isinstance(approval["inventory_run_id"], str) and approval["inventory_run_id"].isdigit(),
            "inventory run ID is required")
    for key in ("approval_ticket", "host_name"):
        require(isinstance(approval[key], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{7,127}", approval[key]),
                f"{key} is missing or unsafe")
    for key in ("measurement_proof", "backup_restore_proof", "rollback_proof", "node_sha256",
                "npm_sha256", "n8n_lock_sha256", "gateway_lock_sha256"):
        require(isinstance(approval[key], str) and re.fullmatch(r"[a-f0-9]{64}", approval[key]),
                f"{key} SHA-256 is required")
    require(approval["os_id"] == "ubuntu" and approval["os_version_id"] == "26.04" and
            approval["architecture"] == "x86_64", "host-native approval requires the inventoried Ubuntu 26.04 x86_64")
    require(approval["node_path"] in {"/usr/bin/node", "/usr/local/bin/node"}, "approved Node path is required")
    require(re.fullmatch(r"v24\.[0-9]+\.[0-9]+", approval["node_version"]) is not None,
            "n8n 2.39.8 requires an exact Node 24 version")
    require(re.fullmatch(r"[a-f0-9]{64}", approval["node_sha256"]) is not None, "Node binary SHA-256 is required")
    require(approval["npm_path"] in {"/usr/bin/npm", "/usr/local/bin/npm"} and
            re.fullmatch(r"(?:10|11)\.[0-9]+\.[0-9]+", approval["npm_version"]) is not None,
            "approved npm 10/11 executable and version are required")
    require(type(approval["postgres_version_num"]) is int and 180000 <= approval["postgres_version_num"] < 190000,
            "approved PostgreSQL major must be 18")
    require(re.fullmatch(r"[a-z][a-z0-9_]{1,62}", approval["finance_database"]) is not None,
            "Finance database name is unsafe")
    require(approval["backend_current_revision"] == "20260822_0019" and
            approval["backend_target_revision"] == "20260921_0025",
            "approved backend migration lineage is not the inventoried path")
    require(approval["ports"] == PORTS, "host-native ports must be the approved loopback-only set")
    capacity = approval["capacity"]
    require(type(capacity) is dict and set(capacity) == CAPACITY_FIELDS, "measured capacity fields are incomplete")
    for key, value in capacity.items():
        require(type(value) is int and value > 0, f"{key} must be a positive measured KiB amount")
    require(capacity["memory_reserve_kib"] >= 512 * 1024, "memory reserve must be at least 512 MiB")
    require(capacity["disk_reserve_kib"] >= 1024 * 1024, "disk reserve must be at least 1 GiB")
    return approval


def required_memory(approval: dict) -> int:
    c = approval["capacity"]
    return sum(c[key] for key in ("n8n_peak_kib", "gateway_peak_kib", "worker_peak_kib", "memory_reserve_kib"))


def required_disk(approval: dict) -> int:
    c = approval["capacity"]
    return sum(c[key] for key in ("install_kib", "database_growth_kib", "backup_kib", "restore_kib", "disk_reserve_kib"))


def validate_facts(approval: dict, facts: dict) -> dict:
    require(facts.get("host_name") == approval["host_name"], "live host differs from approval")
    require(facts.get("os_id") == approval["os_id"] and
            facts.get("os_version_id") == approval["os_version_id"] and
            facts.get("architecture") == approval["architecture"], "live OS or architecture differs from approval")
    require(facts.get("node_version") == approval["node_version"] and
            facts.get("node_sha256") == approval["node_sha256"], "Node binary differs from approval")
    require(facts.get("npm_version") == approval["npm_version"] and
            facts.get("npm_sha256") == approval["npm_sha256"], "npm executable differs from approval")
    require(facts.get("postgres_version_num") == approval["postgres_version_num"] and
            facts.get("postgres_superuser") is True, "PostgreSQL version/admin access is unverified")
    require(facts.get("backend_revision") == approval["backend_current_revision"],
            "Finance database revision differs from approved migration lineage")
    require(facts.get("backend_loopback_healthy") is True, "existing backend loopback health is unavailable")
    require(facts.get("memory_available_kib", 0) >= required_memory(approval),
            f"available memory below measured peak plus reserve ({required_memory(approval)} KiB)")
    require(facts.get("disk_free_kib", 0) >= required_disk(approval),
            f"free disk below install, growth, backup, restore and reserve ({required_disk(approval)} KiB)")
    ports = facts.get("ports", {})
    require(set(ports) == {"n8n", "gateway", "worker"} and
            all(value in {"free", "owned"} for value in ports.values()),
            "host-native loopback port is occupied by an unrelated process")
    require(facts.get("backend_port") == "loopback", "backend must listen only on loopback 8081")
    require(facts.get("production_env_ready") is True, "production credential file is incomplete or unsafe")
    require(facts.get("rollback_gate_ready") is True, "approved non-destructive rollback gate is missing")
    require(facts.get("unit_paths_ready") is True, "systemd unit or backend drop-in is unmanaged")
    return {"mode": "host-native-v1", "memory_required_kib": required_memory(approval),
            "disk_required_kib": required_disk(approval), "host": approval["host_name"],
            "status": "read-only preflight passed; deployment approval is separate"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600


def _production_credentials_ready() -> bool:
    if pwd is None:
        return False
    env_file = Path("/etc/finance/delivery/production.env")
    if not _private_file(env_file) or env_file.stat().st_uid != 0:
        return False
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in values:
            return False
        values[key] = value
    secrets = (
        "FINANCE_N8N_POSTGRES_PASSWORD", "FINANCE_GATEWAY_DB_PASSWORD", "N8N_ENCRYPTION_KEY",
        "FINANCE_GATEWAY_QUEUE_KEY", "FINANCE_GATEWAY_TOKEN", "FINANCE_INGRESS_HMAC_SECRET",
        "FINANCE_CALLBACK_HMAC_SECRET",
    )
    if any(not re.fullmatch(r"[a-f0-9]{64}", values.get(key, "")) for key in secrets):
        return False
    if len({values[key] for key in secrets}) != len(secrets):
        return False
    if not re.fullmatch(r"[A-Za-z0-9._-]{20,256}", values.get("DEEPSEEK_API_KEY", "")):
        return False
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", values.get("DEEPSEEK_MODEL", "")):
        return False
    if values.get("FINANCE_BACKEND_FCM_ENABLED") != "true":
        return False
    project = values.get("FINANCE_BACKEND_FCM_PROJECT_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{4,128}", project):
        return False
    for key, owner in (("FINANCE_BACKEND_FCM_CREDENTIALS_FILE", pwd.getpwnam("finance").pw_uid),
                       ("FINANCE_E2E_BEARER_TOKEN_FILE", 0)):
        raw = values.get(key, "")
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", raw):
            return False
        path = Path(raw)
        if not _private_file(path) or path.stat().st_uid != owner:
            return False
    account = json.loads(Path(values["FINANCE_BACKEND_FCM_CREDENTIALS_FILE"]).read_text(encoding="utf-8"))
    if (account.get("type") != "service_account" or account.get("project_id") != project or
            not account.get("private_key") or not account.get("client_email")):
        return False
    if not Path(values["FINANCE_E2E_BEARER_TOKEN_FILE"]).read_text(encoding="utf-8").strip():
        return False
    try:
        from uuid import UUID
        UUID(values.get("FINANCE_E2E_SNAPSHOT_ID", ""))
    except ValueError:
        return False
    return True


def _os_release() -> dict[str, str]:
    return dict(line.split("=", 1) for line in (
        line.strip() for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
    ) if "=" in line)


def _postgres_query(query: str, database: str = "postgres") -> str:
    result = subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-AtX", "-v", "ON_ERROR_STOP=1",
                             "-d", database, "-c", query], capture_output=True, text=True, check=False, timeout=15)
    require(result.returncode == 0, "read-only local PostgreSQL query failed")
    return result.stdout.strip()


def _owned_unit(key: str) -> bool:
    unit = Path("/etc/systemd/system") / UNITS[key]
    if not unit.is_file() or unit.is_symlink() or not unit.read_text(encoding="utf-8").startswith(MARKER):
        return False
    result = subprocess.run(["systemctl", "is-active", "--quiet", UNITS[key]], capture_output=True, check=False)
    return result.returncode == 0


def _unit_paths_ready() -> bool:
    paths = [Path("/etc/systemd/system") / name for name in UNITS.values()]
    paths.append(Path("/etc/systemd/system/finance-backend.service.d/finance-investment-native.conf"))
    return all(not path.exists() and not path.is_symlink() or
               path.is_file() and not path.is_symlink() and
               path.read_text(encoding="utf-8").startswith(MARKER) for path in paths)


def _loopback_listeners() -> dict[int, list[str]]:
    result = subprocess.run(["ss", "-H", "-ltn"], capture_output=True, text=True, check=False, timeout=5)
    require(result.returncode == 0, "host TCP listeners cannot be inspected")
    listeners: dict[int, list[str]] = {}
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        address = columns[3]
        port_text = address.rsplit(":", 1)[-1]
        if port_text.isdigit():
            listeners.setdefault(int(port_text), []).append(address)
    return listeners


def live_facts(approval: dict) -> dict:
    require(os.geteuid() == 0 and platform.system() == "Linux", "read-only host-native preflight requires Linux root")
    require(shutil.which("runuser") and shutil.which("psql") and shutil.which("pg_dump") and
            shutil.which("pg_restore") and shutil.which("systemctl") and shutil.which("ss"),
            "PostgreSQL, systemd or socket-inspection tooling is missing")
    release = _os_release()
    node = Path(approval["node_path"])
    require(node.is_file() and not node.is_symlink(), "approved Node binary is absent or a symlink")
    npm = Path(approval["npm_path"])
    require(npm.is_file() or npm.is_symlink(), "approved npm executable is absent")
    version = subprocess.run([str(node), "--version"], capture_output=True, text=True, check=False, timeout=5)
    require(version.returncode == 0, "approved Node binary cannot run")
    npm_version = subprocess.run([str(npm), "--version"], capture_output=True, text=True, check=False, timeout=5)
    require(npm_version.returncode == 0, "approved npm executable cannot run")
    memory = next((int(line.split()[1]) for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
                   if line.startswith("MemAvailable:")), 0)
    disk = min(shutil.disk_usage(path).free // 1024 for path in ("/opt", "/var/lib"))
    postgres_version = int(_postgres_query("SHOW server_version_num"))
    superuser = _postgres_query("SELECT rolsuper FROM pg_roles WHERE rolname=current_user") == "t"
    backend_revision = _postgres_query("SELECT version_num FROM public.alembic_version", approval["finance_database"])
    with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=3) as response:
        backend_healthy = response.status == 200
    listeners = _loopback_listeners()
    ports = {}
    for key in ("n8n", "gateway", "worker"):
        addresses = listeners.get(PORTS[key], [])
        ports[key] = ("owned" if addresses == [f"127.0.0.1:{PORTS[key]}"] and _owned_unit(key)
                      else "occupied" if addresses else "free")
    backend_port = "loopback" if listeners.get(8081) == ["127.0.0.1:8081"] else "missing_or_public"
    gate_file = Path("/etc/finance/delivery/rollback-gate.json")
    try:
        credentials_ready = _production_credentials_ready()
    except (OSError, ValueError, KeyError):
        credentials_ready = False
    return {"host_name": socket.gethostname(), "os_id": release.get("ID", "").strip('"'),
            "os_version_id": release.get("VERSION_ID", "").strip('"'), "architecture": platform.machine(),
            "node_version": version.stdout.strip(), "node_sha256": _sha256(node),
            "npm_version": npm_version.stdout.strip(), "npm_sha256": _sha256(npm.resolve()),
            "postgres_version_num": postgres_version, "postgres_superuser": superuser,
            "backend_revision": backend_revision, "backend_loopback_healthy": backend_healthy,
            "memory_available_kib": memory, "disk_free_kib": disk, "ports": ports,
            "backend_port": backend_port, "active_release": Path("/opt/finance/delivery/native/active.json").is_file(),
            "production_env_ready": credentials_ready,
            "rollback_gate_ready": _private_file(gate_file) and gate_file.stat().st_uid == 0,
            "unit_paths_ready": _unit_paths_ready()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("dry-run", "preflight"))
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--facts", type=Path)
    args = parser.parse_args()
    try:
        if args.approval:
            raw = args.approval.read_bytes()
        else:
            encoded = os.environ.get("FINANCE_NATIVE_APPROVAL_B64", "")
            expected = os.environ.get("FINANCE_NATIVE_APPROVAL_SHA256", "")
            require(re.fullmatch(r"[a-f0-9]{64}", expected) is not None, "native approval SHA-256 is required")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ContractError("native approval base64 is invalid") from exc
            require(hashlib.sha256(raw).hexdigest() == expected, "native approval SHA-256 mismatch")
        approval = validate_approval(raw)
        if args.mode == "dry-run":
            require(args.facts is not None, "dry-run requires synthetic --facts")
            facts = json.loads(args.facts.read_text(encoding="utf-8"))
        else:
            require(args.facts is None, "live preflight refuses synthetic facts")
            facts = live_facts(approval)
        print(json.dumps(validate_facts(approval, facts), sort_keys=True))
    except (ContractError, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"NATIVE_PREFLIGHT_BLOCKED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
