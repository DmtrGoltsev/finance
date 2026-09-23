"""Host-side Finance delivery release operations. Never invoked from a workstation."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

from contract import ContractError, check_live_host, require, validate_approval

BASE = Path("/opt/finance/delivery")
CONFIG = Path("/etc/finance/delivery")
BACKUPS = Path("/opt/finance/backups/delivery")
BACKEND_ENV = Path("/etc/finance/backend.env")
SERVICE = Path("/etc/systemd/system/finance-investment-worker.service")
PROXY_SERVICE = Path("/etc/systemd/system/finance-investment-callback-proxy.service")
BACKEND_DROPIN = Path("/etc/systemd/system/finance-backend.service.d/finance-investment-delivery.conf")
GENERATED = CONFIG / "generated.env"
EXTERNAL = CONFIG / "external.env"
BACKEND_SECRET = CONFIG / "backend.env"
WORKER_ENV = CONFIG / "worker.env"
WORKFLOWS = (
    "finance-investment-recommendation-v1",
    "finance-signed-health-v1",
    "finance-metadata-retention-v1",
)
GENERATED_KEYS = (
    "FINANCE_N8N_POSTGRES_PASSWORD", "FINANCE_GATEWAY_DB_PASSWORD",
    "N8N_ENCRYPTION_KEY", "FINANCE_GATEWAY_QUEUE_KEY", "FINANCE_GATEWAY_TOKEN",
    "FINANCE_INGRESS_HMAC_SECRET", "FINANCE_CALLBACK_HMAC_SECRET",
)
PACKAGE_NAMES = {
    "docker_ce": "docker-ce", "docker_ce_cli": "docker-ce-cli",
    "containerd_io": "containerd.io", "docker_buildx_plugin": "docker-buildx-plugin",
    "docker_compose_plugin": "docker-compose-plugin",
}
OWNER_MARKER = "# Managed by Finance investment delivery release contract.\n"
MUTABLE_APPROVAL_FIELDS = {"inventory_run_id", "captured_at_utc", "approved_at_utc", "approval_ticket"}


def run(args: list[str], *, env: dict[str, str] | None = None, input_bytes: bytes | None = None,
        output: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(args, env=env, input=input_bytes, capture_output=True, check=False)
    if result.returncode:
        raise ContractError(f"command failed ({args[0]} {args[1] if len(args) > 1 else ''}); inspect host service status without exposing secrets")
    if output:
        return result
    return result


def read_env(path: Path, *, required: bool = True) -> dict[str, str]:
    if not path.exists():
        require(not required, f"required external file is absent: {path}")
        return {}
    require(path.is_file() and not path.is_symlink(), f"environment file must be a regular file: {path}")
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, f"environment file must have mode 0600: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        require(separator == "=" and re.fullmatch(r"[A-Z][A-Z0-9_]*", key) is not None,
                f"invalid environment line in {path}")
        require(key not in values and "\x00" not in value, f"duplicate or invalid environment key in {path}")
        values[key] = value.strip('"\'')
    return values


def write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as file:
        file.write(content)
        temp = Path(file.name)
    os.chmod(temp, 0o600)
    temp.replace(path)


def write_owned(path: Path, content: str) -> None:
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8").startswith(OWNER_MARKER),
                f"refusing to overwrite unmanaged file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(OWNER_MARKER + content, encoding="utf-8")
    os.chmod(path, 0o644)


def external_secrets() -> dict[str, str]:
    external = read_env(EXTERNAL)
    require(len(external.get("DEEPSEEK_API_KEY", "")) >= 20 and
            not external["DEEPSEEK_API_KEY"].startswith("replace-"), "DEEPSEEK_API_KEY is absent or a placeholder")
    require(external.get("FINANCE_BACKEND_FCM_ENABLED") == "true", "FCM must be explicitly enabled")
    project = external.get("FINANCE_BACKEND_FCM_PROJECT_ID", "")
    require(bool(re.fullmatch(r"[A-Za-z0-9-]{4,128}", project)), "FCM project ID is absent")
    credential_path = Path(external.get("FINANCE_BACKEND_FCM_CREDENTIALS_FILE", ""))
    require(credential_path.is_absolute() and credential_path.is_file() and not credential_path.is_symlink(),
            "FCM service-account file is absent")
    require(stat.S_IMODE(credential_path.stat().st_mode) == 0o600, "FCM service-account file must have mode 0600")
    try:
        credential = json.loads(credential_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ContractError("FCM service-account file is invalid JSON") from exc
    require(credential.get("type") == "service_account" and credential.get("project_id") == project,
            "FCM service-account project does not match")
    require(bool(credential.get("private_key")) and bool(credential.get("client_email")),
            "FCM service-account private key is absent")
    backend = read_env(BACKEND_ENV)
    require(bool(backend.get("FINANCE_BACKEND_DATABASE_URL") or backend.get("DATABASE_URL")),
            "Finance backend database URL is absent")
    token_path = Path(external.get("FINANCE_E2E_BEARER_TOKEN_FILE", ""))
    require(token_path.is_absolute() and token_path.is_file() and not token_path.is_symlink() and
            stat.S_IMODE(token_path.stat().st_mode) == 0o600,
            "Finance e2e bearer-token file is absent or not mode 0600")
    require(bool(token_path.read_text(encoding="utf-8").strip()), "Finance e2e bearer token is empty")
    try:
        UUID(external.get("FINANCE_E2E_SNAPSHOT_ID", ""))
    except ValueError as exc:
        raise ContractError("Finance e2e confirmed snapshot ID is absent or invalid") from exc
    return external


def generated_secrets() -> dict[str, str]:
    if not GENERATED.exists():
        generated = {key: secrets.token_hex(32) for key in GENERATED_KEYS}
        write_private(GENERATED, "".join(f"{key}={value}\n" for key, value in generated.items()))
    generated = read_env(GENERATED)
    require(set(generated) == set(GENERATED_KEYS), "generated secret set is incomplete or unexpected")
    require(all(len(value) == 64 and re.fullmatch(r"[a-f0-9]{64}", value) for value in generated.values()),
            "generated secret format is invalid")
    require(len(set(generated.values())) == len(GENERATED_KEYS), "generated secrets must differ")
    return generated


def ensure_packages(approval: dict) -> None:
    require(os.geteuid() == 0, "Docker installation requires root after approval")
    requested = []
    for key, package in PACKAGE_NAMES.items():
        version = approval["docker_packages"][key]
        current = subprocess.run(["dpkg-query", "-W", "-f=${Version}", package],
                                 capture_output=True, text=True, check=False)
        if current.returncode == 0 and current.stdout.strip() == version:
            continue
        policy = run(["apt-cache", "policy", package], output=True).stdout.decode("utf-8")
        require("download.docker.com" in policy and version in policy,
                f"approved Docker package version is unavailable from official configured repository: {package}")
        requested.append(f"{package}={version}")
    if requested:
        run(["apt-get", "install", "-y", "--no-install-recommends", *requested])
    for key, package in PACKAGE_NAMES.items():
        installed = run(["dpkg-query", "-W", "-f=${Version}", package], output=True).stdout.decode().strip()
        require(installed == approval["docker_packages"][key], f"installed Docker package version mismatch: {package}")
    run(["systemctl", "enable", "--now", "docker"])
    run(["docker", "info", "--format", "{{.ServerVersion}}"])
    run(["docker", "compose", "version", "--short"])


def ensure_bridge(approval: dict) -> None:
    name = approval["bridge_name"]
    inspect = subprocess.run(["docker", "network", "inspect", name], capture_output=True, check=False)
    if inspect.returncode:
        run(["docker", "network", "create", "--driver", "bridge", "--subnet", approval["bridge_subnet"],
             "--gateway", approval["bridge_gateway"], "--label", "com.finance.owner=investment-delivery", name])
        inspect = run(["docker", "network", "inspect", name], output=True)
    network = json.loads(inspect.stdout)[0]
    require(network.get("Driver") == "bridge" and network.get("Labels", {}).get("com.finance.owner") == "investment-delivery",
            "bridge exists but is not owned by Finance delivery")
    ipam = network["IPAM"]["Config"]
    require(len(ipam) == 1 and ipam[0]["Subnet"] == approval["bridge_subnet"] and
            ipam[0]["Gateway"] == approval["bridge_gateway"], "bridge address differs from approval")


def compose_env(approval: dict, external: dict[str, str], generated: dict[str, str], release_id: str) -> dict[str, str]:
    return {**os.environ, **generated, "COMPOSE_PROJECT_NAME": "finance-n8n",
            "FINANCE_N8N_POSTGRES_DB": "finance_n8n", "FINANCE_N8N_POSTGRES_USER": "finance_n8n",
            "FINANCE_GATEWAY_DB": "finance_analysis", "FINANCE_GATEWAY_DB_USER": "finance_analysis",
            "FINANCE_POSTGRES_IMAGE": approval["images"]["postgres"],
            "FINANCE_N8N_IMAGE": approval["images"]["n8n"],
            "FINANCE_GATEWAY_NODE_BASE_IMAGE": approval["images"]["gateway_node_base"],
            "FINANCE_GATEWAY_IMAGE": f"finance-analysis-gateway:{release_id}",
            "FINANCE_DELIVERY_BRIDGE_NAME": approval["bridge_name"],
            "FINANCE_DELIVERY_BRIDGE_GATEWAY": approval["bridge_gateway"],
            "FINANCE_CALLBACK_PROXY_PORT": str(approval["callback_port"]),
            "FINANCE_N8N_LISTEN_PORT": str(approval["n8n_port"]),
            "FINANCE_BACKEND_API_PREFIX": "/api/v1", "DEEPSEEK_API_KEY": external.get("DEEPSEEK_API_KEY", "maintenance-unavailable"),
            "DEEPSEEK_MODEL": external.get("DEEPSEEK_MODEL", "deepseek-v4-pro"), "TZ": "Europe/Moscow"}


def compose(source: Path, env: dict[str, str], *args: str, input_bytes: bytes | None = None,
            output: bool = False) -> subprocess.CompletedProcess:
    return run(["docker", "compose", "-p", "finance-n8n", "-f", str(source / "ops/finance-n8n/compose.yml"),
                *args], env=env, input_bytes=input_bytes, output=output)


def check_compose_network(source: Path, env: dict[str, str]) -> None:
    config = json.loads(compose(source, env, "config", "--format", "json", output=True).stdout)
    services = config["services"]
    require(set(services) == {"postgres", "n8n", "analysis-gateway"}, "unexpected Compose service")
    require(not services["postgres"].get("ports") and not services["analysis-gateway"].get("ports"),
            "database or gateway has a published port")
    ports = services["n8n"].get("ports", [])
    require(len(ports) == 1 and ports[0].get("host_ip") == "127.0.0.1", "n8n must bind only to loopback")
    require("finance_host_bridge" not in services["n8n"].get("networks", {}), "n8n must not join host callback bridge")


def _safe_release_id(value: str) -> str:
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is not None, "unsafe release ID")
    return value


def _release_source(release_id: str) -> Path:
    source = BASE / "releases" / _safe_release_id(release_id)
    require(source.is_dir() and not source.is_symlink(), "staged Finance delivery release is absent")
    return source


def _stage_source(source: Path, release_id: str, approval: dict) -> Path:
    require((source / "ops/finance-n8n/compose.yml").is_file(), "delivery package is incomplete")
    require((source / "ops/finance-release/host_release.py").is_file(), "host contract is missing")
    target = BASE / "releases" / release_id
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=target.parent) as temp:
            staged = Path(temp) / "release"
            staged.mkdir()
            (staged / "ops").mkdir()
            shutil.copytree(source / "ops/finance-n8n", staged / "ops/finance-n8n")
            shutil.copytree(source / "ops/finance-release", staged / "ops/finance-release")
            (staged / "approval.json").write_text(json.dumps(approval, sort_keys=True) + "\n", encoding="utf-8")
            staged.replace(target)
    else:
        require(target.is_dir() and not target.is_symlink(), "release path is not an owned directory")
        existing = json.loads((target / "approval.json").read_text(encoding="utf-8"))
        require({key: value for key, value in existing.items() if key not in MUTABLE_APPROVAL_FIELDS} ==
                {key: value for key, value in approval.items() if key not in MUTABLE_APPROVAL_FIELDS},
                "existing release has a different approved host or version plan")
        for directory in ("ops/finance-n8n", "ops/finance-release"):
            incoming = {path.relative_to(source) for path in (source / directory).rglob("*") if path.is_file()}
            staged = {path.relative_to(target) for path in (target / directory).rglob("*") if path.is_file()}
            require(incoming == staged, "existing release file set differs")
            for relative in incoming:
                require(_file_sha256(target / relative) == _file_sha256(source / relative),
                        f"existing release content differs: {relative}")
        (target / "approval.json").write_text(json.dumps(approval, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _link_current(target: Path) -> None:
    current = BASE / "current"
    require(not current.exists() or current.is_symlink(), "delivery current path is not a symlink")
    next_link = BASE / "current.next"
    require(not next_link.exists() and not next_link.is_symlink(), "stale delivery current.next requires review")
    next_link.symlink_to(target, target_is_directory=True)
    next_link.replace(current)


def _postgres(source: Path, env: dict[str, str], *args: str,
              input_bytes: bytes | None = None, output: bool = False):
    return compose(source, env, "exec", "-T", "postgres", *args,
                   input_bytes=input_bytes, output=output)


def _ensure_gateway_database(source: Path, env: dict[str, str]) -> None:
    def exists(table: str, name: str) -> bool:
        query = f"SELECT 1 FROM {table} WHERE {name}='finance_analysis'"
        result = _postgres(source, env, "psql", "-U", "finance_n8n", "-d", "postgres", "-tAc", query,
                           output=True)
        return result.stdout.strip() == b"1"

    password = env["FINANCE_GATEWAY_DB_PASSWORD"]
    if not exists("pg_roles", "rolname"):
        _postgres(source, env, "psql", "-v", "ON_ERROR_STOP=1", "-U", "finance_n8n", "-d", "postgres",
                  input_bytes=f"CREATE ROLE finance_analysis LOGIN PASSWORD '{password}';\n".encode())
    else:
        _postgres(source, env, "psql", "-v", "ON_ERROR_STOP=1", "-U", "finance_n8n", "-d", "postgres",
                  input_bytes=f"ALTER ROLE finance_analysis PASSWORD '{password}';\n".encode())
    if not exists("pg_database", "datname"):
        _postgres(source, env, "psql", "-v", "ON_ERROR_STOP=1", "-U", "finance_n8n", "-d", "postgres",
                  input_bytes=b"CREATE DATABASE finance_analysis OWNER finance_analysis;\n"
                              b"REVOKE ALL ON DATABASE finance_analysis FROM PUBLIC;\n")
    _postgres(source, env, "sh", "-c", 'PGPASSWORD="$FINANCE_GATEWAY_DB_PASSWORD" psql -v ON_ERROR_STOP=1 '
              '--username "$FINANCE_GATEWAY_DB_USER" --dbname "$FINANCE_GATEWAY_DB" '
              '-f /opt/finance/gateway-schema.sql')


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup(source: Path, env: dict[str, str], release_id: str) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BACKUPS, 0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    destination = BACKUPS / f"{stamp}-{release_id}"
    require(not destination.exists(), "backup destination already exists")
    destination.mkdir(mode=0o700)
    checksums = {}
    for name, database in (("n8n", "finance_n8n"), ("gateway", "finance_analysis")):
        dump = destination / f"{name}.dump"
        command = ["docker", "compose", "-p", "finance-n8n", "-f", str(source / "ops/finance-n8n/compose.yml"),
                   "exec", "-T", "postgres", "pg_dump", "-U", "finance_n8n", "-Fc", "-d", database]
        with dump.open("wb") as file:
            result = subprocess.run(command, env=env, stdout=file, stderr=subprocess.PIPE, check=False)
        require(result.returncode == 0 and dump.stat().st_size > 0, f"{name} backup failed")
        os.chmod(dump, 0o600)
        checksums[dump.name] = _file_sha256(dump)
    secret_copy = destination / "generated.env"
    shutil.copyfile(GENERATED, secret_copy)
    os.chmod(secret_copy, 0o600)
    checksums[secret_copy.name] = _file_sha256(secret_copy)
    write_private(destination / "manifest.json", json.dumps({"release_id": release_id,
                  "created_at_utc": stamp, "sha256": checksums}, sort_keys=True) + "\n")
    return destination


def _verify_backup(path: Path) -> dict:
    require(path.is_dir() and not path.is_symlink() and path.parent == BACKUPS, "backup path is outside Finance delivery")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    require(set(manifest["sha256"]) == {"n8n.dump", "gateway.dump", "generated.env"}, "backup manifest is incomplete")
    for name, digest in manifest["sha256"].items():
        item = path / name
        require(item.is_file() and not item.is_symlink() and _file_sha256(item) == digest,
                f"backup checksum mismatch: {name}")
    return manifest


def _restore_drill(source: Path, env: dict[str, str], backup: Path) -> None:
    _verify_backup(backup)
    stamp = secrets.token_hex(4)
    for label, expected_table in (("n8n", "workflow_entity"), ("gateway", "gateway_runs")):
        database = f"finance_restore_{label}_{stamp}"
        _postgres(source, env, "createdb", "-U", "finance_n8n", database)
        try:
            command = ["docker", "compose", "-p", "finance-n8n", "-f", str(source / "ops/finance-n8n/compose.yml"),
                       "exec", "-T", "postgres", "pg_restore", "-U", "finance_n8n", "--no-owner", "--no-privileges",
                       "-d", database]
            with (backup / f"{label}.dump").open("rb") as dump:
                result = subprocess.run(command, env=env, stdin=dump, capture_output=True, check=False)
            require(result.returncode == 0, f"isolated {label} restore failed")
            query = f"SELECT to_regclass('public.{expected_table}') IS NOT NULL"
            result = _postgres(source, env, "psql", "-U", "finance_n8n", "-d", database, "-tAc", query,
                               output=True)
            require(result.stdout.strip() == b"t", f"restored {label} schema is incomplete")
        finally:
            _postgres(source, env, "dropdb", "-U", "finance_n8n", "--if-exists", database)


def _install_units(approval: dict, external: dict[str, str], generated: dict[str, str]) -> None:
    require(shutil.which("python3") is not None, "host Python 3 is required for callback proxy")
    write_private(BACKEND_SECRET,
                  f"FINANCE_BACKEND_INVESTMENT_CALLBACK_HMAC_SECRET={generated['FINANCE_CALLBACK_HMAC_SECRET']}\n")
    worker_values = {
        "FINANCE_BACKEND_ENVIRONMENT": "production",
        "FINANCE_BACKEND_DATABASE_MIGRATION_POLICY": "external",
        "FINANCE_BACKEND_DELIVERY_N8N_URL":
            f"http://127.0.0.1:{approval['n8n_port']}/webhook/internal/finance/investments/recommendations/v1",
        "FINANCE_BACKEND_DELIVERY_INGRESS_SECRET": generated["FINANCE_INGRESS_HMAC_SECRET"],
        "FINANCE_BACKEND_FCM_ENABLED": "true",
        "FINANCE_BACKEND_FCM_PROJECT_ID": external["FINANCE_BACKEND_FCM_PROJECT_ID"],
        "FINANCE_BACKEND_FCM_CREDENTIALS_FILE": external["FINANCE_BACKEND_FCM_CREDENTIALS_FILE"],
    }
    write_private(WORKER_ENV, "".join(f"{key}={value}\n" for key, value in worker_values.items()))
    write_owned(BACKEND_DROPIN, f"[Service]\nEnvironmentFile={BACKEND_SECRET}\n")
    write_owned(PROXY_SERVICE, f"""[Unit]
Description=Finance investment callback bridge
Requires=docker.service
After=docker.service

[Service]
Type=simple
User=finance
Group=finance
ExecStart={shutil.which('python3')} {BASE}/current/ops/finance-release/callback_proxy.py --bind {approval['bridge_gateway']} --subnet {approval['bridge_subnet']} --port {approval['callback_port']}
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
""")
    write_owned(SERVICE, f"""[Unit]
Description=Finance investment delivery worker
Requires=finance-investment-callback-proxy.service
After=network-online.target finance-investment-callback-proxy.service

[Service]
Type=simple
User=finance
Group=finance
WorkingDirectory=/opt/finance/current/package/apps/backend
EnvironmentFile={BACKEND_ENV}
EnvironmentFile={WORKER_ENV}
ExecStart=/opt/finance/current/venv/bin/python -m app.delivery.worker
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
""")
    run(["systemctl", "daemon-reload"])


def _import_n8n(source: Path, env: dict[str, str], generated: dict[str, str]) -> None:
    credential = [{"id": "finance-gateway-token", "name": "Finance Gateway Internal Token",
                   "type": "httpHeaderAuth", "data": {"name": "X-Finance-Gateway-Token",
                   "value": generated["FINANCE_GATEWAY_TOKEN"]}}]
    script = "umask 077; trap 'rm -f /tmp/finance-gateway-credential.json' EXIT; " \
             "cat > /tmp/finance-gateway-credential.json; " \
             "n8n import:credentials --input=/tmp/finance-gateway-credential.json"
    compose(source, env, "run", "--rm", "-T", "--no-deps", "n8n", "sh", "-c", script,
            input_bytes=json.dumps(credential).encode())
    files = {path.stem for path in (source / "ops/finance-n8n/workflows").glob("*.json")}
    require(files == set(WORKFLOWS), "delivery package must contain exactly three workflows")
    for workflow in WORKFLOWS:
        compose(source, env, "run", "--rm", "-T", "--no-deps", "n8n", "n8n", "import:workflow",
                f"--input=/home/node/.n8n/imports/{workflow}.json")


def _signed_health(port: int, secret: str) -> None:
    path = "/webhook/internal/finance/health/v1"
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    body = b"{}"
    canonical = b"POST\n" + path.encode() + b"\n" + timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body
    signature = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method="POST",
              headers={"Content-Type": "application/octet-stream", "X-Finance-Timestamp": timestamp,
                       "X-Finance-Nonce": nonce, "X-Finance-Signature": signature})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            require(response.status == 200 and json.loads(response.read(4096)).get("status") == "ok",
                    "signed n8n health response is invalid")
    except urllib.error.URLError as exc:
        raise ContractError("signed n8n health failed") from exc


def _context(args, *, maintenance: bool = False) -> tuple[dict, dict[str, str], dict[str, str], Path, dict[str, str]]:
    raw_approval = json.loads(args.approval.read_bytes())
    approved_at = dt.datetime.fromisoformat(raw_approval["approved_at_utc"].replace("Z", "+00:00"))
    approval = validate_approval(args.approval.read_bytes(), now=approved_at) if maintenance else validate_approval(args.approval.read_bytes())
    if not maintenance:
        check_live_host(approval)
    external = read_env(EXTERNAL, required=False) if maintenance else external_secrets()
    generated = read_env(GENERATED, required=False)
    release_id = _safe_release_id(args.release_id)
    source = _release_source(release_id)
    staged = json.loads((source / "approval.json").read_text(encoding="utf-8"))
    require({key: value for key, value in staged.items() if key not in MUTABLE_APPROVAL_FIELDS} ==
            {key: value for key, value in approval.items() if key not in MUTABLE_APPROVAL_FIELDS},
            "live release plan differs from approved staged plan")
    env = compose_env(approval, external, generated, release_id)
    return approval, external, generated, source, env


def stage(args) -> None:
    require(os.geteuid() == 0, "stage requires root")
    approval = validate_approval(args.approval.read_bytes())
    check_live_host(approval)
    external = external_secrets()
    try:
        import pwd
        finance_uid = pwd.getpwnam("finance").pw_uid
    except (ImportError, KeyError) as exc:
        raise ContractError("existing finance service user is required") from exc
    fcm_file = Path(external["FINANCE_BACKEND_FCM_CREDENTIALS_FILE"])
    require(fcm_file.stat().st_uid == finance_uid, "FCM credential must be owned by finance for worker access")
    require(args.source.is_dir() and not args.source.is_symlink(), "source delivery artifact is absent")
    active_file = BASE / "active.json"
    if active_file.exists():
        active = json.loads(active_file.read_text(encoding="utf-8"))
        if active.get("release_id") == args.release_id:
            generated = generated_secrets()
            target = _release_source(args.release_id)
            staged = json.loads((target / "approval.json").read_text(encoding="utf-8"))
            require({key: value for key, value in staged.items() if key not in MUTABLE_APPROVAL_FIELDS} ==
                    {key: value for key, value in approval.items() if key not in MUTABLE_APPROVAL_FIELDS},
                    "active release differs from approved plan")
            require((BASE / "current").is_symlink() and (BASE / "current").resolve() == target,
                    "active release marker disagrees with current symlink")
            env = compose_env(approval, external, generated, args.release_id)
            _health(approval, target, env, generated, worker=True)
            return
    ensure_packages(approval)
    ensure_bridge(approval)
    generated = generated_secrets()
    release_id = _safe_release_id(args.release_id)
    target = _stage_source(args.source, release_id, approval)
    env = compose_env(approval, external, generated, release_id)
    check_compose_network(target, env)
    compose(target, env, "pull", "postgres", "n8n")
    compose(target, env, "build", "--pull", "analysis-gateway")
    existing = subprocess.run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=finance-n8n",
                               "--filter", "label=com.docker.compose.service=postgres"],
                              capture_output=True, check=False)
    if existing.stdout.strip():
        previous = BASE / "current"
        require(previous.is_symlink(), "existing Finance n8n stack has no owned current release")
        old_source = previous.resolve(strict=True)
        old_id = _safe_release_id(old_source.name)
        old_approval = json.loads((old_source / "approval.json").read_text(encoding="utf-8"))
        old_env = compose_env(old_approval, external, generated, old_id)
        if SERVICE.exists():
            run(["systemctl", "stop", "finance-investment-worker.service"])
        compose(old_source, old_env, "stop", "n8n", "analysis-gateway")
        _backup(old_source, old_env, old_id)
    compose(target, env, "up", "-d", "--wait", "postgres")
    _ensure_gateway_database(target, env)
    compose(target, env, "up", "-d", "--wait", "postgres", "analysis-gateway", "n8n")
    backup = _backup(target, env, release_id)
    _restore_drill(target, env, backup)
    _link_current(target)
    _install_units(approval, external, generated)
    run(["systemctl", "enable", "--now", "finance-investment-callback-proxy.service"])
    _import_n8n(target, env, generated)
    rows = _postgres(target, env, "psql", "-U", "finance_n8n", "-d", "finance_n8n", "-tAc",
                     "SELECT id || '|' || active FROM workflow_entity ORDER BY id", output=True).stdout.decode().splitlines()
    require(set(rows) == {f"{workflow}|false" for workflow in WORKFLOWS},
            "n8n must contain exactly three inactive Finance workflows after import")
    print(f"Finance delivery staged; release={release_id}; backup={backup}; workflows=3 inactive")


def _health(approval: dict, source: Path, env: dict[str, str], generated: dict[str, str], *, worker: bool) -> None:
    compose(source, env, "ps", "--all")
    for service in ("postgres", "analysis-gateway", "n8n"):
        container = compose(source, env, "ps", "-q", service, output=True).stdout.decode().strip()
        require(bool(container), f"{service} container is absent")
        state = run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container], output=True).stdout.decode().strip()
        require(state == "healthy", f"{service} is not healthy")
    _signed_health(approval["n8n_port"], generated["FINANCE_INGRESS_HMAC_SECRET"])
    compose(source, env, "exec", "-T", "analysis-gateway", "node", "-e",
            f"fetch('http://finance-host-callback:{approval['callback_port']}/healthz')"
            ".then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))")
    if worker:
        run(["systemctl", "is-active", "--quiet", "finance-investment-worker.service"])
        try:
            with urllib.request.urlopen("http://127.0.0.1:8091/healthz", timeout=5) as response:
                require(response.status == 200, "worker health returned an error")
        except urllib.error.URLError as exc:
            raise ContractError("worker health is unavailable") from exc
    print("Finance delivery health: postgres, gateway, n8n, signed webhook, bridge callback, worker PASS")


def _e2e(external: dict[str, str], release_id: str) -> None:
    token_path = Path(external["FINANCE_E2E_BEARER_TOKEN_FILE"])
    token = token_path.read_text(encoding="utf-8").strip()
    snapshot_id = str(UUID(external["FINANCE_E2E_SNAPSHOT_ID"]))
    base = "http://127.0.0.1:8081/api/v1/investments/recommendation-jobs"

    def request(path: str, payload: dict | None = None) -> tuple[int, dict]:
        body = json.dumps(payload).encode() if payload is not None else None
        call = urllib.request.Request(base + path, data=body, method="POST" if body else "GET",
                                      headers={"Authorization": f"Bearer {token}",
                                               "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(call, timeout=20) as response:
                return response.status, json.loads(response.read(1024 * 1024))
        except (urllib.error.URLError, ValueError) as exc:
            raise ContractError("Finance e2e API request failed; inspect backend status without exposing token") from exc

    e2e_key = "finance-delivery-e2e-" + hashlib.sha256(release_id.encode()).hexdigest()
    status, created = request("", {"idempotencyKey": e2e_key,
                                   "snapshotIds": [snapshot_id]})
    require(status == 202 and isinstance(created.get("data", {}).get("id"), str),
            "Finance e2e job creation failed")
    job_id = str(UUID(created["data"]["id"]))
    for _ in range(60):
        status, found = request(f"/{job_id}")
        require(status == 200, "Finance e2e job lookup failed")
        state = found.get("data", {}).get("status")
        if state == "ready":
            report_status, report = request(f"/{job_id}/report")
            require(report_status == 200 and report.get("data", {}).get("jobId") == job_id,
                    "Finance e2e report does not match completed job")
            print(f"Finance delivery e2e: job={job_id}; report=ready")
            return
        require(state in {"queued", "collecting", "analyzing"}, f"Finance e2e job failed: {state}")
        time.sleep(10)
    raise ContractError("Finance e2e job did not complete within 10 minutes")


def activate(args) -> None:
    require(os.geteuid() == 0, "activate requires root")
    approval, external, generated, source, env = _context(args)
    require((BASE / "current").is_symlink() and (BASE / "current").resolve() == source,
            "delivery release is not current")
    backend = Path("/opt/finance/current")
    require(backend.is_symlink() and backend.resolve().name == args.release_id,
            "backend must be switched to the same release before activation")
    require(Path("/opt/finance/current/venv/bin/python").is_file(), "backend release Python is absent")
    for workflow in WORKFLOWS:
        compose(source, env, "run", "--rm", "-T", "--no-deps", "n8n", "n8n", "publish:workflow",
                f"--id={workflow}")
    compose(source, env, "restart", "n8n")
    for _attempt in range(12):
        try:
            _signed_health(approval["n8n_port"], generated["FINANCE_INGRESS_HMAC_SECRET"])
            break
        except ContractError:
            time.sleep(5)
    else:
        raise ContractError("signed health did not recover after workflow activation")
    run(["systemctl", "enable", "--now", "finance-investment-worker.service"])
    _health(approval, source, env, generated, worker=True)
    _e2e(external, args.release_id)
    write_private(BASE / "active.json", json.dumps({"release_id": args.release_id}, sort_keys=True) + "\n")
    print(f"Finance delivery activated; release={args.release_id}; workflows=3")


def backup(args) -> None:
    _approval, _external, _generated, source, env = _context(args)
    destination = _backup(source, env, args.release_id)
    print(f"Finance delivery backup complete: {destination}")


def restore_drill(args) -> None:
    _approval, _external, _generated, source, env = _context(args)
    _restore_drill(source, env, args.backup.resolve())
    print("Finance delivery isolated restore drill: PASS")


def restore(args) -> None:
    require(args.confirm == "RESTORE_FINANCE_DELIVERY_DATABASES", "explicit restore confirmation is required")
    require(os.geteuid() == 0, "restore requires root")
    _approval, _external, _generated, source, env = _context(args)
    selected = args.backup.resolve()
    _verify_backup(selected)
    safety = _backup(source, env, args.release_id)
    run(["systemctl", "stop", "finance-investment-worker.service"])
    compose(source, env, "stop", "n8n", "analysis-gateway")
    for label, database in (("n8n", "finance_n8n"), ("gateway", "finance_analysis")):
        command = ["docker", "compose", "-p", "finance-n8n", "-f", str(source / "ops/finance-n8n/compose.yml"),
                   "exec", "-T", "postgres", "pg_restore", "-U", "finance_n8n", "--clean", "--if-exists",
                   "--no-owner", "--no-privileges", "-d", database]
        with (selected / f"{label}.dump").open("rb") as dump:
            result = subprocess.run(command, env=env, stdin=dump, capture_output=True, check=False)
        require(result.returncode == 0, f"production {label} restore failed; safety backup={safety}")
    shutil.copyfile(selected / "generated.env", GENERATED)
    os.chmod(GENERATED, 0o600)
    generated = generated_secrets()
    env = compose_env(_approval, _external, generated, args.release_id)
    compose(source, env, "up", "-d", "--wait", "postgres", "analysis-gateway", "n8n")
    run(["systemctl", "start", "finance-investment-worker.service"])
    _health(_approval, source, env, generated, worker=True)
    print(f"Finance delivery databases restored; pre-restore safety backup={safety}")


def rollback(args) -> None:
    require(os.geteuid() == 0, "rollback requires root")
    approval, external, generated, source, env = _context(args, maintenance=True)
    require((BASE / "current").is_symlink() and (BASE / "current").resolve() == source,
            "current delivery release changed; rollback refused")
    run(["systemctl", "stop", "finance-investment-worker.service"])
    if args.stop_new:
        compose(source, env, "stop", "n8n", "analysis-gateway")
        run(["systemctl", "stop", "finance-investment-callback-proxy.service"])
        (BASE / "active.json").unlink(missing_ok=True)
        print("Finance delivery stopped; both databases and generated secrets preserved")
        return
    external = external_secrets()
    previous = _release_source(_safe_release_id(args.previous_release_id))
    previous_approval = json.loads((previous / "approval.json").read_text(encoding="utf-8"))
    require(previous_approval["bridge_subnet"] == approval["bridge_subnet"] and
            previous_approval["bridge_gateway"] == approval["bridge_gateway"],
            "rollback cannot change the live bridge")
    compose(source, env, "stop", "n8n", "analysis-gateway")
    _link_current(previous)
    _install_units(previous_approval, external, generated)
    old_env = compose_env(previous_approval, external, generated, args.previous_release_id)
    compose(previous, old_env, "up", "-d", "--wait", "postgres", "analysis-gateway", "n8n")
    run(["systemctl", "restart", "finance-investment-callback-proxy.service"])
    _signed_health(previous_approval["n8n_port"], generated["FINANCE_INGRESS_HMAC_SECRET"])
    run(["systemctl", "start", "finance-investment-worker.service"])
    _health(previous_approval, previous, old_env, generated, worker=True)
    write_private(BASE / "active.json", json.dumps({"release_id": args.previous_release_id}, sort_keys=True) + "\n")
    print(f"Finance delivery rolled back to {args.previous_release_id}; DB data preserved")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stage", "activate", "health", "backup", "restore-drill", "restore", "rollback"))
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--confirm")
    parser.add_argument("--previous-release-id")
    parser.add_argument("--stop-new", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == "stage":
            require(args.source is not None, "stage requires --source")
            stage(args)
        elif args.command == "activate":
            activate(args)
        elif args.command == "health":
            approval, _external, generated, source, env = _context(args)
            _health(approval, source, env, generated, worker=True)
        elif args.command == "backup":
            backup(args)
        elif args.command == "restore-drill":
            require(args.backup is not None, "restore-drill requires --backup")
            restore_drill(args)
        elif args.command == "restore":
            require(args.backup is not None, "restore requires --backup")
            restore(args)
        elif args.command == "rollback":
            require(args.stop_new or args.previous_release_id, "rollback requires --previous-release-id or --stop-new")
            rollback(args)
    except (ContractError, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"DELIVERY_RELEASE_BLOCKED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
