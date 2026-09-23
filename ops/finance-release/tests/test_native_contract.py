from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import native_contract
import native_release


def approval(now: dt.datetime) -> dict:
    return {
        "mode": "host-native-v1", "inventory_run_id": "123456789",
        "captured_at_utc": (now - dt.timedelta(hours=1)).isoformat(),
        "approved_at_utc": (now - dt.timedelta(minutes=10)).isoformat(),
        "approval_ticket": "FIN-NATIVE-123", "measurement_proof": "a" * 64,
        "backup_restore_proof": "b" * 64, "rollback_proof": "c" * 64,
        "host_name": "finance-host", "os_id": "ubuntu", "os_version_id": "26.04",
        "architecture": "x86_64", "node_path": "/usr/bin/node", "node_version": "v24.0.0",
        "node_sha256": "d" * 64, "npm_path": "/usr/bin/npm", "npm_version": "10.9.2",
        "npm_sha256": "e" * 64, "n8n_lock_sha256": "f" * 64,
        "gateway_lock_sha256": "0" * 64, "postgres_version_num": 180006,
        "finance_database": "finance", "backend_current_revision": "20260822_0019",
        "backend_target_revision": "20260921_0025", "ports": native_contract.PORTS.copy(),
        "capacity": {
            "n8n_peak_kib": 1280 * 1024, "gateway_peak_kib": 256 * 1024,
            "worker_peak_kib": 256 * 1024, "memory_reserve_kib": 512 * 1024,
            "install_kib": 1024 * 1024, "database_growth_kib": 512 * 1024,
            "backup_kib": 512 * 1024, "restore_kib": 512 * 1024,
            "disk_reserve_kib": 1024 * 1024,
        },
    }


def facts(approved: dict) -> dict:
    return {
        "host_name": approved["host_name"], "os_id": approved["os_id"],
        "os_version_id": approved["os_version_id"], "architecture": approved["architecture"],
        "node_version": approved["node_version"], "node_sha256": approved["node_sha256"],
        "npm_version": approved["npm_version"], "npm_sha256": approved["npm_sha256"],
        "postgres_version_num": approved["postgres_version_num"], "postgres_superuser": True,
        "backend_revision": approved["backend_current_revision"], "backend_loopback_healthy": True,
        "memory_available_kib": native_contract.required_memory(approved),
        "disk_free_kib": native_contract.required_disk(approved),
        "ports": {key: "free" for key in ("n8n", "gateway", "worker")},
        "backend_port": "loopback", "active_release": False,
        "production_env_ready": True, "rollback_gate_ready": True, "unit_paths_ready": True,
    }


class NativeApprovalTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 9, 23, 12, tzinfo=dt.timezone.utc)
        self.plan = approval(self.now)

    def validated(self):
        return native_contract.validate_approval(json.dumps(self.plan).encode(), self.now)

    def test_complete_read_only_plan_has_explicit_capacity(self):
        plan = self.validated()
        self.assertEqual(native_contract.validate_facts(plan, facts(plan))["status"],
                         "read-only preflight passed; deployment approval is separate")

    def test_cli_dry_run_uses_only_synthetic_facts(self):
        plan = approval(dt.datetime.now(dt.timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            approval_path = Path(temp) / "approval.json"
            facts_path = Path(temp) / "facts.json"
            approval_path.write_text(json.dumps(plan), encoding="utf-8")
            facts_path.write_text(json.dumps(facts(plan)), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "native_contract.py"), "dry-run",
                                     "--approval", str(approval_path), "--facts", str(facts_path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["mode"], "host-native-v1")

    def test_docker_mode_stale_inventory_and_unpinned_node_fail(self):
        self.plan["mode"] = "docker"
        with self.assertRaisesRegex(native_contract.ContractError, "Docker approval"):
            self.validated()
        self.plan = approval(self.now)
        self.plan["captured_at_utc"] = (self.now - dt.timedelta(days=2)).isoformat()
        with self.assertRaisesRegex(native_contract.ContractError, "stale"):
            self.validated()
        self.plan = approval(self.now)
        self.plan["node_sha256"] = "unknown"
        with self.assertRaisesRegex(native_contract.ContractError, "SHA-256"):
            self.validated()
        self.plan = approval(self.now)
        self.plan["node_version"] = "v22.15.0"
        with self.assertRaisesRegex(native_contract.ContractError, "Node 24"):
            self.validated()

    def test_observed_vps_resources_and_occupied_port_fail_before_mutation(self):
        plan = self.validated()
        live = facts(plan)
        live["memory_available_kib"] = 2_126_744
        with self.assertRaisesRegex(native_contract.ContractError, "memory"):
            native_contract.validate_facts(plan, live)
        live = facts(plan)
        live["disk_free_kib"] = 3_530_780
        with self.assertRaisesRegex(native_contract.ContractError, "disk"):
            native_contract.validate_facts(plan, live)
        live = facts(plan)
        live["ports"]["gateway"] = "occupied"
        with self.assertRaisesRegex(native_contract.ContractError, "port"):
            native_contract.validate_facts(plan, live)

    def test_missing_credentials_rollback_or_pg_admin_fail(self):
        plan = self.validated()
        for field in ("production_env_ready", "rollback_gate_ready", "postgres_superuser", "unit_paths_ready"):
            live = facts(plan)
            live[field] = False
            with self.assertRaises(native_contract.ContractError):
                native_contract.validate_facts(plan, live)


class NativeInstallerTests(unittest.TestCase):
    def test_workflow_keeps_host_native_path_behind_unconditional_hold(self):
        workflow = (REPO / ".github/workflows/finance-hexcore-prod-deploy.yml").read_text(encoding="utf-8")
        ref_guard = workflow.split("  reject-inventory-ref:", 1)[1].split("  prepare-release:", 1)[0]
        self.assertIn('"${GITHUB_REF}" != refs/heads/prod/release-*', ref_guard)
        self.assertIn('"${GITHUB_REF}" != refs/heads/main', ref_guard)
        self.assertIn('if [[ "${GITHUB_REF}" != refs/heads/prod/release-* ]]; then', workflow)
        gate = workflow.split("  production-package-gate:", 1)[1].split("  host-preflight:", 1)[0]
        self.assertIn("DELIVERY_HOST_NATIVE_CAPACITY_UNVERIFIED", gate)
        self.assertIn('exit 1\n          else', gate)
        self.assertIn("native_contract.py", workflow)
        self.assertIn("native_release.py\" stage", workflow)
        self.assertIn("native_release.py activate", workflow)
        self.assertIn("rollback-delivery-on-failure:", workflow)

    def test_lockfile_and_registry_integrity_are_checked(self):
        plan = approval(dt.datetime.now(dt.timezone.utc))
        plan["n8n_lock_sha256"] = hashlib.sha256(
            (ROOT / "native-n8n/package-lock.json").read_bytes()).hexdigest()
        plan["gateway_lock_sha256"] = hashlib.sha256(
            (REPO / "ops/finance-n8n/package-lock.json").read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            shutil.copytree(ROOT / "native-n8n", source / "ops/finance-release/native-n8n",
                            ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
            shutil.copytree(REPO / "ops/finance-n8n", source / "ops/finance-n8n",
                            ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
            native_release.check_source(source, plan)
            plan["n8n_lock_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "lockfile differs"):
                native_release.check_source(source, plan)

    def test_stage_preflight_failure_never_starts_backup_or_install(self):
        with tempfile.TemporaryDirectory() as temp:
            args = SimpleNamespace(release_id="test-release", approval=Path(temp) / "approval.json",
                                   source=Path(temp))
            with (patch.object(native_release, "BASE", Path(temp) / "base"),
                  patch.object(native_release, "preflight", side_effect=ValueError("capacity blocked")),
                  patch.object(native_release, "_backup_and_drill") as backup,
                  patch.object(native_release, "command") as command):
                with self.assertRaisesRegex(ValueError, "capacity blocked"):
                    native_release.stage(args)
                backup.assert_not_called()
                command.assert_not_called()

    def test_finance_writable_root_code_or_changed_hash_blocks_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "release"
            modules = target / "ops/finance-release"
            modules.mkdir(parents=True)
            hashes = {}
            for name in ("contract.py", "host_release.py", "native_contract.py", "native_release.py"):
                file = modules / name
                file.write_text("approved source\n", encoding="utf-8")
                hashes[file.relative_to(target).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
            (target / "source-hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
            writable = modules / "native_release.py"
            with (patch.object(native_release, "_root_locked", side_effect=lambda path: path != writable),
                  self.assertRaisesRegex(ValueError, "writable or not root-owned")):
                native_release._verify_source_provenance(target)
            writable.write_text("modified source\n", encoding="utf-8")
            with (patch.object(native_release, "_root_locked", return_value=True),
                  self.assertRaisesRegex(ValueError, "provenance differs")):
                native_release._verify_source_provenance(target)

    def test_database_conflict_blocks_password_change(self):
        calls = []

        def fake_pg(query, database="postgres"):
            calls.append(query)
            if "FROM pg_authid" in query:
                return "false|false|false|finance-investment-delivery"
            if "FROM pg_database" in query:
                return "other_owner|unmanaged"
            raise AssertionError("database was mutated before ownership check")

        with (patch.object(native_release, "pg", side_effect=fake_pg),
              self.assertRaisesRegex(ValueError, "database is not owned")):
            native_release._ensure_database("finance_n8n", "finance_n8n", "a" * 64)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any("ALTER ROLE" in query for query in calls))

    def test_restage_never_reuses_stale_backup(self):
        dumps = []

        def fake_run(args, **kwargs):
            if "pg_dump" in args:
                dumps.append(args)
                kwargs["stdout"].write(f"fresh-{len(dumps)}".encode())
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as temp:
            with (patch.object(native_release, "BACKUPS", Path(temp)),
                  patch.object(native_release, "pg"),
                  patch.object(native_release.subprocess, "run", side_effect=fake_run)):
                first = native_release._backup_and_drill("finance", "release-1")
                second = native_release._backup_and_drill("finance", "release-1")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"fresh-1")
            self.assertEqual(second.read_bytes(), b"fresh-2")
            self.assertEqual(len(dumps), 2)

    def test_production_env_rejects_missing_provider_secret(self):
        values = {key: f"{index:064x}" for index, key in enumerate(native_release.SECRET_KEYS, 1)}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "production.env"
            path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
            with (patch.object(native_release, "PRODUCTION", path),
                  patch.object(native_release, "private_file"),
                  patch.object(native_release, "read_env", return_value=values),
                  self.assertRaisesRegex(ValueError, "DeepSeek credential")):
                native_release.production_env()
            values["DEEPSEEK_API_KEY"] = "ci-test-only-provider-key-long"
            values["DEEPSEEK_MODEL"] = "approved-model"
            with (patch.object(native_release, "PRODUCTION", path),
                  patch.object(native_release, "private_file"),
                  patch.object(native_release, "read_env", return_value=values),
                  self.assertRaisesRegex(ValueError, "FCM is not explicitly enabled")):
                native_release.production_env()

    def test_production_env_rejects_unsafe_provider_value(self):
        values = {key: f"{index:064x}" for index, key in enumerate(native_release.SECRET_KEYS, 1)}
        values["DEEPSEEK_API_KEY"] = "provider-key with embedded spaces"
        with (patch.object(native_release, "private_file"),
              patch.object(native_release, "read_env", return_value=values),
              self.assertRaisesRegex(ValueError, "DeepSeek credential")):
            native_release.production_env()

    def test_evidence_hash_mismatch_blocks_before_rollback_claims(self):
        plan = approval(dt.datetime.now(dt.timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp)
            (config / "measurement.json").write_text("{}", encoding="utf-8")
            with (patch.object(native_release, "CONFIG", config),
                  patch.object(native_release, "private_file"),
                  self.assertRaisesRegex(ValueError, "measurement evidence SHA-256")):
                native_release.evidence(plan, "test-release")

    def test_missing_copy_migration_proof_blocks_before_mutation(self):
        plan = approval(dt.datetime.now(dt.timezone.utc))
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp)
            measurement = {"inventory_run_id": plan["inventory_run_id"], "host_name": plan["host_name"],
                           "capacity": plan["capacity"]}
            backup = {"finance_database": plan["finance_database"],
                      "inventory_run_id": plan["inventory_run_id"], "restore_drill_confirmed": True}
            gate = {"release_id": "test-release", "inventory_run_id": plan["inventory_run_id"],
                    "operator_ticket": plan["approval_ticket"], "previous_backend_release_id": "old-release",
                    "backend_schema_forward_compatible": True, "finance_backup_restore_tested": True}
            for name, value, key in (("measurement", measurement, "measurement_proof"),
                                     ("backup-restore", backup, "backup_restore_proof"),
                                     ("rollback-gate", gate, "rollback_proof")):
                file = config / f"{name}.json"
                file.write_text(json.dumps(value), encoding="utf-8")
                plan[key] = hashlib.sha256(file.read_bytes()).hexdigest()
            with (patch.object(native_release, "CONFIG", config),
                  patch.object(native_release, "ROLLBACK_GATE", config / "rollback-gate.json"),
                  patch.object(native_release, "private_file"),
                  self.assertRaisesRegex(ValueError, "rollback gate fields")):
                native_release.evidence(plan, "test-release")

    def test_native_workflow_builder_uses_only_loopback_gateway(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(["node", str(REPO / "ops/finance-n8n/scripts/build-workflows.mjs")],
                                    env={**os.environ, "FINANCE_GATEWAY_HOST_MODE": "native",
                                         "FINANCE_WORKFLOW_OUTPUT_DIR": temp},
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            files = list(Path(temp).glob("*.json"))
            self.assertEqual(len(files), 3)
            for file in files:
                workflow = json.loads(file.read_text(encoding="utf-8"))
                self.assertFalse(workflow["active"])
                self.assertTrue(all(node["parameters"]["url"].startswith("http://127.0.0.1:8080/")
                                    for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.httpRequest"))


if __name__ == "__main__":
    unittest.main()
