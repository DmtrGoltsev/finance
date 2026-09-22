"""Host-native Finance delivery lifecycle. Production workflow remains held."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import time
import urllib.request
from pathlib import Path
from uuid import UUID

try:
    import pwd
except ImportError:  # Local dry-run tests also run on Windows.
    pwd = None

from contract import ContractError, require
from host_release import (
    _e2e,
    _file_sha256,
    _safe_release_id,
    _signed_health,
    read_env,
    write_private,
)
from native_contract import (
    MARKER,
    UNITS,
    _loopback_listeners,
    live_facts,
    validate_approval,
    validate_facts,
)

BASE = Path("/opt/finance/delivery/native")
BACKUPS = Path("/opt/finance/backups/delivery-native")
CONFIG = Path("/etc/finance/delivery")
PRODUCTION = CONFIG / "production.env"
ROLLBACK_GATE = CONFIG / "rollback-gate.json"
BACKEND_DROPIN = Path("/etc/systemd/system/finance-backend.service.d/finance-investment-native.conf")
WORKFLOWS = ("finance-investment-recommendation-v1", "finance-signed-health-v1", "finance-metadata-retention-v1")
SECRET_KEYS = (
    "FINANCE_N8N_POSTGRES_PASSWORD", "FINANCE_GATEWAY_DB_PASSWORD", "N8N_ENCRYPTION_KEY",
    "FINANCE_GATEWAY_QUEUE_KEY", "FINANCE_GATEWAY_TOKEN", "FINANCE_INGRESS_HMAC_SECRET",
    "FINANCE_CALLBACK_HMAC_SECRET",
)


def command(args: list[str], *, env: dict[str, str] | None = None, input_bytes: bytes | None = None,
            user: str | None = None, timeout: int = 600, cwd: Path | None = None) -> bytes:
    require(not user or pwd is not None, "POSIX user switching is unavailable")
    identity = pwd.getpwnam(user) if user else None
    result = subprocess.run(args, env=env, input=input_bytes, cwd=cwd, capture_output=True, check=False, timeout=timeout,
                            user=identity.pw_uid if identity else None, group=identity.pw_gid if identity else None)
    require(result.returncode == 0, f"command failed: {Path(args[0]).name}; inspect local service status without secrets")
    return result.stdout


def private_file(path: Path, *, owner: int | None = None) -> None:
    require(path.is_file() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600,
            f"private production file is absent or not mode 0600: {path}")
    if owner is not None:
        require(path.stat().st_uid == owner, f"private production file has wrong owner: {path}")


def production_env() -> dict[str, str]:
    private_file(PRODUCTION, owner=0)
    values = read_env(PRODUCTION)
    for key in SECRET_KEYS:
        require(re.fullmatch(r"[a-f0-9]{64}", values.get(key, "")) is not None,
                f"{key} must be a distinct 64-character production secret")
    require(len({values[key] for key in SECRET_KEYS}) == len(SECRET_KEYS), "production secrets must differ")
    require(re.fullmatch(r"[A-Za-z0-9._-]{20,256}", values.get("DEEPSEEK_API_KEY", "")) is not None and
            not values["DEEPSEEK_API_KEY"].startswith("replace"), "DeepSeek credential is missing or unsafe")
    require(re.fullmatch(r"[A-Za-z0-9._-]{1,80}", values.get("DEEPSEEK_MODEL", "")) is not None,
            "approved DeepSeek model is missing")
    require(values.get("FINANCE_BACKEND_FCM_ENABLED") == "true", "FCM is not explicitly enabled")
    project = values.get("FINANCE_BACKEND_FCM_PROJECT_ID", "")
    require(re.fullmatch(r"[A-Za-z0-9-]{4,128}", project) is not None, "FCM project ID is missing")
    uid = pwd.getpwnam("finance").pw_uid
    fcm = Path(values.get("FINANCE_BACKEND_FCM_CREDENTIALS_FILE", ""))
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+", str(fcm)) is not None,
            "FCM service-account path must be an absolute safe path")
    private_file(fcm, owner=uid)
    try:
        account = json.loads(fcm.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ContractError("FCM service-account JSON is invalid") from exc
    require(account.get("type") == "service_account" and account.get("project_id") == project and
            bool(account.get("private_key")) and bool(account.get("client_email")),
            "FCM service account is incomplete or for another project")
    token = Path(values.get("FINANCE_E2E_BEARER_TOKEN_FILE", ""))
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+", str(token)) is not None,
            "e2e token path must be an absolute safe path")
    private_file(token, owner=0)
    require(bool(token.read_text(encoding="utf-8").strip()), "e2e bearer token is empty")
    try:
        UUID(values.get("FINANCE_E2E_SNAPSHOT_ID", ""))
    except ValueError as exc:
        raise ContractError("confirmed e2e snapshot UUID is missing") from exc
    return values


def evidence(approval: dict, release_id: str) -> dict:
    for name, key in (("measurement", "measurement_proof"),
                      ("backup-restore", "backup_restore_proof"), ("rollback-gate", "rollback_proof")):
        path = CONFIG / f"{name}.json"
        private_file(path, owner=0)
        require(_file_sha256(path) == approval[key], f"{name} evidence SHA-256 differs from approval")
    measurement = json.loads((CONFIG / "measurement.json").read_text(encoding="utf-8"))
    require(measurement.get("inventory_run_id") == approval["inventory_run_id"] and
            measurement.get("host_name") == approval["host_name"] and
            measurement.get("capacity") == approval["capacity"], "capacity measurement does not match approval")
    backup = json.loads((CONFIG / "backup-restore.json").read_text(encoding="utf-8"))
    require(backup.get("finance_database") == approval["finance_database"] and
            backup.get("inventory_run_id") == approval["inventory_run_id"] and
            backup.get("restore_drill_confirmed") is True,
            "Finance backup/restore evidence is absent")
    private_file(ROLLBACK_GATE, owner=0)
    gate = json.loads(ROLLBACK_GATE.read_text(encoding="utf-8"))
    require(set(gate) == {"release_id", "inventory_run_id", "previous_backend_release_id",
                          "backend_schema_forward_compatible", "finance_backup_restore_tested",
                          "copy_migration_0019_to_0025_tested", "previous_backend_on_migrated_copy_tested",
                          "operator_ticket"}, "rollback gate fields are incomplete")
    require(gate["release_id"] == release_id and gate["inventory_run_id"] == approval["inventory_run_id"] and
            gate["operator_ticket"] == approval["approval_ticket"], "rollback gate differs from approval")
    require(gate["backend_schema_forward_compatible"] is True and
            gate["finance_backup_restore_tested"] is True and
            gate["copy_migration_0019_to_0025_tested"] is True and
            gate["previous_backend_on_migrated_copy_tested"] is True,
            "migration on a copy and non-destructive backend rollback are not approved")
    previous = _safe_release_id(gate["previous_backend_release_id"])
    require((Path("/opt/finance/releases") / previous / "venv/bin/python").is_file(),
            "previous backend release is absent; rollback would be impossible")
    return gate


def check_source(source: Path, approval: dict) -> None:
    require(source.is_dir() and not source.is_symlink(), "native artifact source is absent")
    require(not any(path.is_symlink() for path in source.rglob("*")), "native source contains a symlink")
    lock = source / "ops/finance-release/native-n8n/package-lock.json"
    gateway_lock = source / "ops/finance-n8n/package-lock.json"
    for file in (lock, gateway_lock, source / "ops/finance-n8n/scripts/build-workflows.mjs"):
        require(file.is_file() and not file.is_symlink(), f"native package file is absent: {file.name}")
    require(_file_sha256(lock) == approval["n8n_lock_sha256"] and
            _file_sha256(gateway_lock) == approval["gateway_lock_sha256"],
            "native package lockfile differs from approval")
    package = json.loads((source / "ops/finance-release/native-n8n/package.json").read_text(encoding="utf-8"))
    locked = json.loads(lock.read_text(encoding="utf-8"))
    require(package.get("dependencies") == {"n8n": "2.39.8"} and
            locked.get("packages", {}).get("node_modules/n8n", {}).get("version") == "2.39.8",
            "n8n 2.39.8 is not exactly locked")
    for entry in locked.get("packages", {}).values():
        if entry.get("resolved", "").startswith("https://"):
            require(entry["resolved"].startswith("https://registry.npmjs.org/") and bool(entry.get("integrity")),
                    "n8n transitive package lacks approved registry URL or integrity hash")
    files = {path.stem for path in (source / "ops/finance-n8n/workflows").glob("*.json")}
    require(files == set(WORKFLOWS), "native package must contain exactly three Finance workflows")


def preflight(approval_path: Path, release_id: str, source: Path) -> tuple[dict, dict[str, str], dict]:
    require(os.geteuid() == 0, "native preflight requires root")
    approval = validate_approval(approval_path.read_bytes())
    validate_facts(approval, live_facts(approval))
    secrets_env = production_env()
    gate = evidence(approval, release_id)
    check_source(source, approval)
    current = Path("/opt/finance/current")
    require(current.is_symlink() and current.resolve().name == gate["previous_backend_release_id"],
            "backend current release differs from rollback gate")
    return approval, secrets_env, gate


def pg(query: str, database: str = "postgres") -> str:
    return command(["runuser", "-u", "postgres", "--", "psql", "-AtX", "-v", "ON_ERROR_STOP=1",
                    "-d", database], input_bytes=query.encode()).decode().strip()


def _ensure_database(role: str, database: str, password: str) -> None:
    require(re.fullmatch(r"[a-z_]+", role) and re.fullmatch(r"[a-z_]+", database), "unsafe database identity")
    require(re.fullmatch(r"[a-f0-9]{64}", password) is not None, "unsafe database password")
    role_info = pg(f"SELECT rolsuper || '|' || rolcreatedb || '|' || rolcreaterole || '|' || "
                   f"coalesce(shobj_description(oid,'pg_authid'),'') FROM pg_authid WHERE rolname='{role}';")
    if not role_info:
        pg(f"BEGIN; CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}'; "
           f"COMMENT ON ROLE {role} IS 'finance-investment-delivery'; COMMIT;")
    else:
        require(role_info == "false|false|false|finance-investment-delivery",
                f"existing PostgreSQL role is not owned by Finance delivery: {role}")
        pg(f"ALTER ROLE {role} PASSWORD '{password}';")
    db_info = pg(f"SELECT pg_get_userbyid(datdba) || '|' || coalesce(shobj_description(oid,'pg_database'),'') "
                 f"FROM pg_database WHERE datname='{database}';")
    if not db_info:
        pg(f"CREATE DATABASE {database} OWNER {role};")
        pg(f"REVOKE ALL ON DATABASE {database} FROM PUBLIC; "
           f"COMMENT ON DATABASE {database} IS 'finance-investment-delivery';")
    else:
        require(db_info == f"{role}|finance-investment-delivery",
                f"existing PostgreSQL database is not owned by Finance delivery: {database}")


def _backup_and_drill(database: str, release_id: str) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BACKUPS, 0o700)
    backup = BACKUPS / f"{release_id}-{database}.dump"
    if not backup.exists():
        with backup.open("wb") as file:
            result = subprocess.run(["runuser", "-u", "postgres", "--", "pg_dump", "-Fc", "-d", database],
                                    stdout=file, stderr=subprocess.PIPE, check=False, timeout=1800)
        require(result.returncode == 0 and backup.stat().st_size > 0, f"{database} backup failed")
        os.chmod(backup, 0o600)
        write_private(backup.with_suffix(".sha256"), _file_sha256(backup) + "\n")
    require(backup.is_file() and not backup.is_symlink() and
            backup.with_suffix(".sha256").read_text(encoding="ascii").strip() == _file_sha256(backup),
            "backup integrity failed")
    temp_db = f"finance_restore_{secrets.token_hex(4)}"
    pg(f"CREATE DATABASE {temp_db};")
    try:
        with backup.open("rb") as dump:
            result = subprocess.run(["runuser", "-u", "postgres", "--", "pg_restore", "--no-owner",
                                     "--no-privileges", "-d", temp_db], stdin=dump, capture_output=True,
                                    check=False, timeout=1800)
        require(result.returncode == 0, f"{database} isolated restore drill failed")
    finally:
        pg(f"DROP DATABASE {temp_db} WITH (FORCE);")
    return backup


def _source_hashes(source: Path) -> dict[str, str]:
    require(not any(path.is_symlink() for path in source.rglob("*")), "native source contains a symlink")
    return {str(path.relative_to(source)): _file_sha256(path) for path in source.rglob("*")
            if path.is_file() and "node_modules" not in path.parts and "__pycache__" not in path.parts}


def _stage_source(source: Path, release_id: str) -> Path:
    target = BASE / "releases" / _safe_release_id(release_id)
    hashes = _source_hashes(source)
    if target.exists():
        require(target.is_dir() and not target.is_symlink(), "native release directory is not owned")
        manifest = target / "source-hashes.json"
        require(manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8")) == hashes,
                "staged source differs from approved artifact")
        require(all((target / name).is_file() and _file_sha256(target / name) == digest
                    for name, digest in hashes.items()), "staged source content changed")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, symlinks=False, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
        write_private(target / "source-hashes.json", json.dumps(hashes, sort_keys=True) + "\n")
    return target


def _finance_env(source: dict[str, str]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    n8n = {
        "DB_TYPE": "postgresdb", "DB_POSTGRESDB_HOST": "127.0.0.1", "DB_POSTGRESDB_PORT": "5432",
        "DB_POSTGRESDB_DATABASE": "finance_n8n", "DB_POSTGRESDB_USER": "finance_n8n",
        "DB_POSTGRESDB_PASSWORD": source["FINANCE_N8N_POSTGRES_PASSWORD"],
        "N8N_ENCRYPTION_KEY": source["N8N_ENCRYPTION_KEY"], "N8N_LISTEN_ADDRESS": "127.0.0.1",
        "N8N_HOST": "127.0.0.1", "N8N_PORT": "5680", "N8N_PROTOCOL": "http",
        "WEBHOOK_URL": "http://127.0.0.1:5680/", "N8N_USER_FOLDER": "/var/lib/finance/n8n",
        "N8N_DIAGNOSTICS_ENABLED": "false", "N8N_TEMPLATES_ENABLED": "false",
        "N8N_VERSION_NOTIFICATIONS_ENABLED": "false", "N8N_BLOCK_ENV_ACCESS_IN_NODE": "true",
        "NODES_EXCLUDE": '["n8n-nodes-base.code","n8n-nodes-base.executeCommand","n8n-nodes-base.readWriteFile"]',
        "EXECUTIONS_DATA_SAVE_ON_SUCCESS": "none", "EXECUTIONS_DATA_SAVE_ON_ERROR": "none",
        "N8N_DEFAULT_BINARY_DATA_MODE": "filesystem", "N8N_PAYLOAD_SIZE_MAX": "1",
        "N8N_RESTRICT_FILE_ACCESS_TO": "/var/lib/finance/n8n", "N8N_RUNNERS_ENABLED": "false",
    }
    gateway = {
        "FINANCE_GATEWAY_HOST_MODE": "native", "FINANCE_GATEWAY_DB": "finance_analysis",
        "FINANCE_GATEWAY_DB_USER": "finance_analysis",
        "FINANCE_GATEWAY_DB_PASSWORD": source["FINANCE_GATEWAY_DB_PASSWORD"],
        "FINANCE_GATEWAY_TOKEN": source["FINANCE_GATEWAY_TOKEN"],
        "FINANCE_GATEWAY_QUEUE_KEY": source["FINANCE_GATEWAY_QUEUE_KEY"],
        "FINANCE_INGRESS_HMAC_SECRET": source["FINANCE_INGRESS_HMAC_SECRET"],
        "FINANCE_CALLBACK_HMAC_SECRET": source["FINANCE_CALLBACK_HMAC_SECRET"],
        "FINANCE_BACKEND_API_PREFIX": "/api/v1", "DEEPSEEK_API_KEY": source["DEEPSEEK_API_KEY"],
        "DEEPSEEK_MODEL": source["DEEPSEEK_MODEL"],
    }
    worker = {
        "FINANCE_BACKEND_ENVIRONMENT": "production", "FINANCE_BACKEND_DATABASE_MIGRATION_POLICY": "external",
        "FINANCE_BACKEND_DELIVERY_N8N_URL":
            "http://127.0.0.1:5680/webhook/internal/finance/investments/recommendations/v1",
        "FINANCE_BACKEND_DELIVERY_INGRESS_SECRET": source["FINANCE_INGRESS_HMAC_SECRET"],
        "FINANCE_BACKEND_FCM_ENABLED": "true",
        "FINANCE_BACKEND_FCM_PROJECT_ID": source["FINANCE_BACKEND_FCM_PROJECT_ID"],
        "FINANCE_BACKEND_FCM_CREDENTIALS_FILE": source["FINANCE_BACKEND_FCM_CREDENTIALS_FILE"],
    }
    return n8n, gateway, worker


def _env_text(values: dict[str, str]) -> str:
    require(all("\n" not in value and "\r" not in value and "\x00" not in value for value in values.values()),
            "production secret has an invalid line break")
    return "".join(f"{key}={value}\n" for key, value in values.items())


def _owned_unit(path: Path, body: str) -> None:
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8").startswith(MARKER),
                f"refusing to overwrite unmanaged systemd unit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MARKER + body, encoding="utf-8")
    os.chmod(path, 0o644)


def _install_units(approval: dict, values: dict[str, str], target: Path) -> None:
    n8n, gateway, worker = _finance_env(values)
    for name, env in (("n8n", n8n), ("gateway", gateway), ("worker", worker)):
        write_private(CONFIG / f"native-{name}.env", _env_text(env))
    write_private(CONFIG / "native-backend.env",
                  _env_text({"FINANCE_BACKEND_INVESTMENT_CALLBACK_HMAC_SECRET":
                             values["FINANCE_CALLBACK_HMAC_SECRET"]}))
    _owned_unit(BACKEND_DROPIN, f"[Service]\nEnvironmentFile={CONFIG / 'native-backend.env'}\n")
    node = approval["node_path"]
    n8n_bin = target / "ops/finance-release/native-n8n/node_modules/n8n/bin/n8n"
    gateway_script = target / "ops/finance-n8n/gateway/server.mjs"
    for name, exec_start, workdir, readwrite in (
        ("n8n", f"{node} {n8n_bin} start", "/var/lib/finance/n8n", "/var/lib/finance/n8n"),
        ("gateway", f"{node} {gateway_script}", str(target / "ops/finance-n8n"), "/var/lib/finance"),
        ("worker", "/opt/finance/current/venv/bin/python -m app.delivery.worker",
         "/opt/finance/current/package/apps/backend", "/var/lib/finance"),
    ):
        unit = Path("/etc/systemd/system") / UNITS[name]
        _owned_unit(unit, f"""[Unit]
Description=Finance host-native investment {name}
After=network-online.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=finance
Group=finance
WorkingDirectory={workdir}
{"EnvironmentFile=/etc/finance/backend.env" if name == "worker" else ""}
EnvironmentFile={CONFIG / f'native-{name}.env'}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths={readwrite}
{"InaccessiblePaths=/var/lib/finance/n8n" if name == "gateway" else ""}

[Install]
WantedBy=multi-user.target
""")
    command(["systemctl", "daemon-reload"])


def _n8n_cli(target: Path, approval: dict, values: dict[str, str], *args: str) -> bytes:
    n8n, _gateway, _worker = _finance_env(values)
    env = {**os.environ, **n8n, "HOME": "/var/lib/finance", "PATH": str(Path(approval["node_path"]).parent) + ":/usr/bin:/bin"}
    return command([approval["node_path"], str(target / "ops/finance-release/native-n8n/node_modules/n8n/bin/n8n"),
                    *args], env=env, user="finance", timeout=300)


def _import_workflows(target: Path, approval: dict, values: dict[str, str]) -> None:
    credential_path = Path("/var/lib/finance/n8n/.finance-gateway-credential.json")
    credential = [{"id": "finance-gateway-token", "name": "Finance Gateway Internal Token",
                   "type": "httpHeaderAuth", "data": {"name": "X-Finance-Gateway-Token",
                   "value": values["FINANCE_GATEWAY_TOKEN"]}}]
    write_private(credential_path, json.dumps(credential) + "\n")
    os.chown(credential_path, pwd.getpwnam("finance").pw_uid, pwd.getpwnam("finance").pw_gid)
    try:
        _n8n_cli(target, approval, values, "import:credentials", f"--input={credential_path}")
    finally:
        credential_path.unlink(missing_ok=True)
    for workflow in WORKFLOWS:
        _n8n_cli(target, approval, values, "import:workflow",
                 f"--input={target / 'ops/finance-release/native-workflows' / (workflow + '.json')}")
    rows = pg("SELECT id || '|' || active FROM workflow_entity ORDER BY id;", "finance_n8n").splitlines()
    require(set(rows) == {f"{workflow}|false" for workflow in WORKFLOWS},
            "n8n must contain exactly three inactive Finance workflows")


def _assert_loopback_bind(*ports: int) -> None:
    listeners = _loopback_listeners()
    for port in ports:
        require(listeners.get(port) == [f"127.0.0.1:{port}"],
                f"Finance native port {port} is not exclusively bound to loopback")


def stage(args) -> None:
    release_id = _safe_release_id(args.release_id)
    active = BASE / "active.json"
    if active.exists():
        require(json.loads(active.read_text(encoding="utf-8")).get("release_id") == release_id,
                "native upgrade requires a separately proven rollback plan")
        approval = validate_approval(args.approval.read_bytes())
        check_source(args.source, approval)
        require((BASE / "releases" / release_id / "approval.json").read_bytes() == args.approval.read_bytes(),
                "active native release approval differs from staged approval")
        health(release_id)
        return
    approval, values, _gate = preflight(args.approval, release_id, args.source)
    _backup_and_drill(approval["finance_database"], release_id)
    target = _stage_source(args.source, release_id)
    write_private(target / "approval.json", args.approval.read_text(encoding="utf-8"))
    finance = pwd.getpwnam("finance")
    finance_home = Path("/var/lib/finance")
    finance_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(finance_home, finance.pw_uid, finance.pw_gid)
    for path in (target, *target.rglob("*")):
        os.chown(path, finance.pw_uid, finance.pw_gid)
    runtime = target / "ops/finance-release/native-n8n"
    gateway = target / "ops/finance-n8n"
    command([approval["npm_path"], "ci", "--omit=dev", "--no-audit", "--no-fund"],
            env={**os.environ, "HOME": "/var/lib/finance"}, user="finance", timeout=1800, cwd=runtime)
    command([approval["npm_path"], "ci", "--omit=dev", "--no-audit", "--no-fund"],
            env={**os.environ, "HOME": "/var/lib/finance"}, user="finance", timeout=600, cwd=gateway)
    require((runtime / "node_modules/n8n/package.json").is_file(), "n8n runtime install is incomplete")
    installed = json.loads((runtime / "node_modules/n8n/package.json").read_text(encoding="utf-8"))
    require(installed.get("version") == "2.39.8", "installed n8n version differs from lockfile")
    native_workflows = target / "ops/finance-release/native-workflows"
    command([approval["node_path"], str(gateway / "scripts/build-workflows.mjs")],
            env={**os.environ, "FINANCE_GATEWAY_HOST_MODE": "native",
                 "FINANCE_WORKFLOW_OUTPUT_DIR": str(native_workflows)}, user="finance")
    require(all("http://127.0.0.1:8080/" in (native_workflows / (name + ".json")).read_text(encoding="utf-8")
                for name in WORKFLOWS), "native workflow gateway URL is not loopback")
    _ensure_database("finance_n8n", "finance_n8n", values["FINANCE_N8N_POSTGRES_PASSWORD"])
    _ensure_database("finance_analysis", "finance_analysis", values["FINANCE_GATEWAY_DB_PASSWORD"])
    for role, database, password in (
        ("finance_n8n", "finance_n8n", values["FINANCE_N8N_POSTGRES_PASSWORD"]),
        ("finance_analysis", "finance_analysis", values["FINANCE_GATEWAY_DB_PASSWORD"]),
    ):
        command(["psql", "-h", "127.0.0.1", "-U", role, "-d", database, "-AtX", "-c", "SELECT 1"],
                env={**os.environ, "PGPASSWORD": password}, user="finance", timeout=10)
    pg("SET ROLE finance_analysis;\n" + (gateway / "postgres/gateway-schema.sql").read_text(encoding="utf-8"),
       "finance_analysis")
    n8n_data = finance_home / "n8n"
    n8n_data.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(n8n_data, finance.pw_uid, finance.pw_gid)
    _install_units(approval, values, target)
    command(["systemctl", "enable", "--now", UNITS["gateway"]])
    command(["systemctl", "enable", "--now", UNITS["n8n"]])
    for _ in range(24):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5680/healthz", timeout=3) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(5)
    else:
        raise ContractError("native n8n did not become healthy before workflow import")
    _assert_loopback_bind(5680, 8080)
    _import_workflows(target, approval, values)
    for database in ("finance_n8n", "finance_analysis"):
        _backup_and_drill(database, release_id)
    current = BASE / "current"
    next_link = BASE / "current.next"
    require(not next_link.exists() and not next_link.is_symlink(), "stale native symlink requires review")
    next_link.symlink_to(target, target_is_directory=True)
    next_link.replace(current)
    write_private(BASE / "staged.json", json.dumps({"release_id": release_id,
                  "previous_backend_release_id": _gate["previous_backend_release_id"]}) + "\n")
    print(f"Finance native stage complete: {release_id}; 3 workflows inactive; Finance/new DB restore drills PASS")


def health(release_id: str) -> None:
    _assert_loopback_bind(5680, 8080, 8091)
    for key in ("n8n", "gateway", "worker"):
        command(["systemctl", "is-active", "--quiet", UNITS[key]])
    for port in (5680, 8080, 8091):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
            require(response.status == 200, f"native health failed on {port}")
    print(f"Finance native health PASS: {release_id}")


def rollback(release_id: str, previous: str) -> None:
    require(os.geteuid() == 0, "native rollback requires root")
    _safe_release_id(release_id)
    _safe_release_id(previous)
    backend_previous = Path("/opt/finance/releases") / previous
    require((backend_previous / "venv/bin/python").is_file(), "previous backend release is missing")
    staged_file = BASE / "staged.json"
    if staged_file.is_file():
        staged = json.loads(staged_file.read_text(encoding="utf-8"))
        require(staged.get("release_id") == release_id and staged.get("previous_backend_release_id") == previous,
                "rollback target differs from recorded native stage")
    current = Path("/opt/finance/current")
    require(current.is_symlink() and current.resolve().name in {release_id, previous},
            "backend current is not an expected release symlink")
    if BACKEND_DROPIN.exists():
        require(BACKEND_DROPIN.is_file() and not BACKEND_DROPIN.is_symlink() and
                BACKEND_DROPIN.read_text(encoding="utf-8").startswith(MARKER),
                "refusing to remove unmanaged backend drop-in")
    for key in ("worker", "n8n", "gateway"):
        unit = Path("/etc/systemd/system") / UNITS[key]
        if unit.exists():
            require(unit.is_file() and not unit.is_symlink() and
                    unit.read_text(encoding="utf-8").startswith(MARKER),
                    f"refusing to stop unmanaged service: {UNITS[key]}")
            command(["systemctl", "disable", "--now", UNITS[key]])
            state = subprocess.run(["systemctl", "is-active", "--quiet", UNITS[key]],
                                   capture_output=True, check=False)
            require(state.returncode != 0, f"native {key} service is still active")
    release = BASE / "releases" / release_id
    approval_file = release / "approval.json"
    if approval_file.is_file():
        try:
            raw_approval = approval_file.read_bytes()
            approved = dt.datetime.fromisoformat(json.loads(raw_approval)["approved_at_utc"].replace("Z", "+00:00"))
            approval = validate_approval(raw_approval, now=approved)
            values = read_env(PRODUCTION)
            for workflow in WORKFLOWS:
                _n8n_cli(release, approval, values, "unpublish:workflow", f"--id={workflow}")
        except (ContractError, OSError, ValueError, KeyError):
            pass  # Services are stopped even if credentials or n8n CLI are unavailable.
    temporary = current.with_name("current.native-rollback")
    require(not temporary.exists() and not temporary.is_symlink(), "stale backend rollback symlink")
    temporary.symlink_to(backend_previous, target_is_directory=True)
    temporary.replace(current)
    if BACKEND_DROPIN.exists():
        BACKEND_DROPIN.unlink()
        command(["systemctl", "daemon-reload"])
    command(["systemctl", "restart", "finance-backend.service"])
    with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=10) as response:
        require(response.status == 200, "previous backend did not recover")
    (BASE / "active.json").unlink(missing_ok=True)
    print("Finance native rollback: backend reverted; new DBs and backups preserved; no migration downgrade")


def activate(args) -> None:
    release_id = _safe_release_id(args.release_id)
    staged = json.loads((BASE / "staged.json").read_text(encoding="utf-8"))
    require(staged["release_id"] == release_id, "native stage does not match backend cutover")
    previous = _safe_release_id(staged["previous_backend_release_id"])
    require(Path("/opt/finance/current").is_symlink() and Path("/opt/finance/current").resolve().name == release_id,
            "backend must be on the same release before native activation")
    approval = validate_approval(args.approval.read_bytes())
    require((BASE / "releases" / release_id / "approval.json").read_bytes() == args.approval.read_bytes(),
            "activation approval differs from staged approval")
    require(pg("SELECT version_num FROM public.alembic_version;", approval["finance_database"]) ==
            approval["backend_target_revision"], "backend migration target is not reached")
    values = production_env()
    target = BASE / "releases" / release_id
    try:
        for workflow in WORKFLOWS:
            _n8n_cli(target, approval, values, "publish:workflow", f"--id={workflow}")
        command(["systemctl", "restart", UNITS["n8n"]])
        command(["systemctl", "enable", "--now", UNITS["worker"]])
        _signed_health(5680, values["FINANCE_INGRESS_HMAC_SECRET"])
        health(release_id)
        _e2e(values, release_id)
        write_private(BASE / "active.json", json.dumps({"release_id": release_id}) + "\n")
    except (ContractError, OSError, ValueError):
        rollback(release_id, previous)
        raise
    print(f"Finance native activation PASS: {release_id}; 3 workflows, worker, signed health and job/report")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "stage", "activate", "health", "rollback"))
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--previous-backend-id")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action in {"preflight", "stage", "activate"}:
            require(args.approval is not None, "approval file is required")
        if args.action in {"preflight", "stage"}:
            require(args.source is not None, "verified source artifact is required")
        if args.action == "preflight":
            preflight(args.approval, args.release_id, args.source)
            print("Finance native preflight PASS; no host mutation")
        elif args.action == "stage":
            stage(args)
        elif args.action == "activate":
            activate(args)
        elif args.action == "health":
            health(args.release_id)
        elif args.action == "rollback":
            require(args.previous_backend_id is not None, "previous backend release ID is required")
            rollback(args.release_id, args.previous_backend_id)
    except (ContractError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"NATIVE_RELEASE_BLOCKED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
