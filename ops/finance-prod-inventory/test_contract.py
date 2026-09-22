from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from validate_output import FIELDS, parse_inventory


ROOT = Path(__file__).resolve().parents[2]
OPS = Path(__file__).resolve().parent
WORKFLOW = ROOT / ".github/workflows/finance-prod-readonly-inventory.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/finance-hexcore-prod-deploy.yml"


def bash() -> str:
    if os.name == "nt":
        return r"C:\Program Files\Git\bin\bash.exe"
    return shutil.which("bash") or "bash"


class InventoryEvidenceTests(unittest.TestCase):
    def valid_data(self) -> bytes:
        values = {key: next(iter(allowed)) for key, allowed in FIELDS.items()}
        values["schema"] = "finance_inventory_v2"
        return "".join(f"{key}={value}\n" for key, value in values.items()).encode()

    def test_host_script_emits_complete_fixed_schema(self) -> None:
        result = subprocess.run(
            [bash(), str(OPS / "inventory.sh")],
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stderr, b"")
        self.assertEqual(set(parse_inventory(result.stdout)), set(FIELDS))

    def test_host_script_schema_with_docker_metadata_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fake_docker = directory / "docker"
            fake_docker.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  'info'|'compose version') exit 0 ;;\n"
                "  *'network inspect'*'.Internal'*) echo true ;;\n"
                "  *'network inspect'*'.Containers'*) echo finance-n8n-gateway ;;\n"
                "  *'ps -aq'*) echo container-id ;;\n"
                "  *'volume ls'*) echo finance-n8n_finance_n8n_data ;;\n"
                "esac\n",
                encoding="ascii",
            )
            fake_docker.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [bash(), str(OPS / "inventory.sh")],
                env=env,
                capture_output=True,
                check=True,
            )
            parsed = parse_inventory(result.stdout)
            self.assertEqual(parsed["docker_daemon_accessible"], "yes")
            self.assertEqual(parsed["backend_network_internal"], "yes")
            self.assertEqual(parsed["n8n_volume_exists"], "yes")

    def test_rejects_unknown_duplicate_missing_and_arbitrary_values(self) -> None:
        valid = self.valid_data()
        for bad in (
            valid + b"extra_field=yes\n",
            valid + b"schema=finance_inventory_v2\n",
            valid.replace(b"schema=finance_inventory_v2\n", b""),
            valid.replace(b"provider_credential_presence=unknown", b"provider_credential_presence=secret"),
            valid.replace(b"backend_current_scope=", b"backend_current_scope=/opt/finance/"),
            valid + b"password=not-a-secret\n",
            valid + b"\xff",
            valid.replace(b"\n", b"\r\n"),
        ):
            with self.subTest(bad=bad[-50:]):
                with self.assertRaises(ValueError):
                    parse_inventory(bad)

    def test_no_secret_values_are_read_by_host_script(self) -> None:
        source = (OPS / "inventory.sh").read_text(encoding="utf-8")
        for forbidden in (
            "docker inspect",
            ".Config.Env",
            "backend.env\"",
            "source /etc/finance",
            ". /etc/finance",
            "printenv",
            "/proc/",
        ):
            self.assertNotIn(forbidden, source)


class WorkflowGuardTests(unittest.TestCase):
    def test_deploy_blocks_inventory_ref_before_any_other_job(self) -> None:
        workflow = yaml.load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        jobs = workflow["jobs"]
        guard = jobs["reject-inventory-ref"]
        self.assertNotIn("environment", guard)
        self.assertNotIn("needs", guard)
        self.assertEqual(set(jobs) - {"reject-inventory-ref"}, self._descendants(jobs, "reject-inventory-ref"))
        script = guard["steps"][0]["run"]
        for event in ("push", "workflow_dispatch"):
            for ref, allowed in (
                ("refs/heads/prod/release-inventory-123", False),
                ("refs/heads/prod/release-inventory-evil", False),
                ("refs/heads/prod/release-finance-123", True),
                ("refs/heads/main", True),
            ):
                with self.subTest(event=event, ref=ref):
                    result = subprocess.run(
                        [bash(), "-c", script],
                        env={**os.environ, "GITHUB_EVENT_NAME": event, "GITHUB_REF": ref},
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode == 0, allowed)

    @staticmethod
    def _descendants(jobs: dict, ancestor: str) -> set[str]:
        reachable = {ancestor}
        while True:
            expanded = reachable | {
                name for name, job in jobs.items()
                if set([job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs", [])) & reachable
            }
            if expanded == reachable:
                return reachable - {ancestor}
            reachable = expanded

    def test_two_phase_permissions_and_environment_boundary(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        jobs = workflow["jobs"]
        self.assertNotIn("push", workflow["on"])
        self.assertEqual(jobs["bootstrap"]["permissions"], {"contents": "write", "actions": "write"})
        self.assertEqual(jobs["validate-inventory"]["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(jobs["inventory"]["permissions"], {"contents": "read"})
        self.assertNotIn("environment", jobs["bootstrap"])
        self.assertNotIn("environment", jobs["validate-inventory"])
        self.assertEqual(jobs["inventory"]["environment"], {"name": "production", "deployment": "false"})
        self.assertIn("refs/heads/main", jobs["bootstrap"]["if"])
        self.assertIn("github.actor == 'DmtrGoltsev'", jobs["bootstrap"]["if"])
        self.assertIn("github.actor == 'github-actions[bot]'", jobs["validate-inventory"]["if"])
        self.assertIn("github.run_attempt == 1", jobs["validate-inventory"]["if"])
        self.assertEqual(jobs["inventory"]["needs"], "validate-inventory")
        self.assertIn("needs.validate-inventory.result == 'success'", jobs["inventory"]["if"])
        self.assertIn("${{ github.token }}", jobs["bootstrap"]["steps"][-1]["env"]["GH_TOKEN"])
        self.assertIn("StrictHostKeyChecking=yes", jobs["inventory"]["steps"][1]["run"])
        self.assertIn("validate_output.py", jobs["inventory"]["steps"][1]["run"])
        for job in jobs.values():
            for step in job["steps"]:
                if "run" in step:
                    checked = subprocess.run(
                        [bash(), "-n"],
                        input=step["run"],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_inventory_guard_rejects_wrong_origin_before_environment(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        script = workflow["jobs"]["validate-inventory"]["steps"][0]["run"]
        valid_run = {
            "id": 123,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "head_sha": "a" * 40,
            "actor": {"login": "DmtrGoltsev"},
            "status": "in_progress",
            "workflow_id": 987,
            "display_title": "finance-inventory-bootstrap-none",
            "run_attempt": 1,
        }
        valid_inventory = {
            "id": 456,
            "event": "workflow_dispatch",
            "head_branch": "prod/release-inventory-123",
            "head_sha": "a" * 40,
            "actor": {"login": "github-actions[bot]"},
            "workflow_id": 987,
            "display_title": "finance-inventory-inventory-123",
            "run_attempt": 1,
        }
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fake_gh = directory / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *'/actions/workflows/finance-prod-readonly-inventory.yml'*) echo 987 ;;\n"
                "  *'/actions/runs/123'*) printf '%s\\n' \"$FAKE_BOOTSTRAP_RUN_JSON\" ;;\n"
                "  *'/actions/runs/456'*) printf '%s\\n' \"$FAKE_INVENTORY_RUN_JSON\" ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="ascii",
            )
            fake_gh.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_REF": "refs/heads/prod/release-inventory-123",
                    "GITHUB_SHA": "a" * 40,
                    "GITHUB_REPOSITORY": "test/finance",
                    "FINANCE_BOOTSTRAP_RUN_ID": "123",
                    "FINANCE_PHASE": "inventory",
                    "GITHUB_RUN_ID": "456",
                    "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "GITHUB_ACTOR": "github-actions[bot]",
                    "GITHUB_RUN_ATTEMPT": "1",
                    "PYTHON_BIN": sys.executable.replace("\\", "/"),
                    "PATH": str(directory) + os.pathsep + env.get("PATH", ""),
                }
            )
            cases = [(valid_run, valid_inventory, "github-actions[bot]", "inventory", True)]
            for key, value in (
                ("head_sha", "b" * 40),
                ("head_branch", "prod/release-inventory-123"),
                ("status", "completed"),
                ("workflow_id", 988),
                ("display_title", "foreign-bootstrap"),
                ("run_attempt", 2),
                ("id", 999),
            ):
                changed = dict(valid_run)
                changed[key] = value
                cases.append((changed, valid_inventory, "github-actions[bot]", "inventory", False))
            changed = dict(valid_run)
            changed["actor"] = {"login": "someone-else"}
            cases.append((changed, valid_inventory, "github-actions[bot]", "inventory", False))
            for key, value in (
                ("actor", {"login": "DmtrGoltsev"}),
                ("head_sha", "b" * 40),
                ("head_branch", "main"),
                ("event", "push"),
                ("workflow_id", 988),
                ("display_title", "finance-inventory-bootstrap-none"),
                ("run_attempt", 2),
                ("id", 999),
            ):
                changed = dict(valid_inventory)
                changed[key] = value
                cases.append((valid_run, changed, "github-actions[bot]", "inventory", False))
            cases.append((valid_run, valid_inventory, "DmtrGoltsev", "inventory", False))
            cases.append((valid_run, valid_inventory, "github-actions[bot]", "bootstrap", False))
            for bootstrap_run, inventory_run, actor, phase, expected in cases:
                env["FAKE_BOOTSTRAP_RUN_JSON"] = json.dumps(bootstrap_run)
                env["FAKE_INVENTORY_RUN_JSON"] = json.dumps(inventory_run)
                env["GITHUB_ACTOR"] = actor
                env["FINANCE_PHASE"] = phase
                result = subprocess.run(
                    [bash(), "-c", script], env=env, capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode == 0, expected, result.stderr)
            env["FAKE_BOOTSTRAP_RUN_JSON"] = json.dumps(valid_run)
            env["FAKE_INVENTORY_RUN_JSON"] = json.dumps(valid_inventory)
            env["GITHUB_ACTOR"] = "github-actions[bot]"
            env["FINANCE_PHASE"] = "inventory"
            for key, value in (
                ("GITHUB_REF", "refs/heads/prod/release-inventory-999"),
                ("GITHUB_SHA", "b" * 40),
                ("GITHUB_RUN_ID", "999"),
                ("GITHUB_RUN_ATTEMPT", "2"),
                ("GITHUB_EVENT_NAME", "push"),
            ):
                with self.subTest(key=key):
                    changed_env = {**env, key: value}
                    result = subprocess.run(
                        [bash(), "-c", script], env=changed_env,
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertNotEqual(result.returncode, 0)

    def test_bootstrap_creates_only_own_ref_and_checks_sha_before_delete(self) -> None:
        source = (OPS / "bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn('branch="prod/release-inventory-${GITHUB_RUN_ID}"', source)
        self.assertIn('[[ "$remote_sha" != "$GITHUB_SHA" ]]', source)
        self.assertIn("-f 'inputs[phase]=inventory'", source)
        self.assertIn('dispatched=yes', source)
        self.assertIn('X-GitHub-Api-Version: 2026-03-10', source)
        self.assertIn('workflow_run_id', source)
        self.assertNotIn('/runs?branch=', source)
        self.assertIn("cleanup_if_owned", source)
        self.assertNotIn("git push", source)
        self.assertNotIn("PERSONAL_ACCESS_TOKEN", source)

    def test_bootstrap_success_dispatches_then_cleans_own_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            calls = directory / "calls"
            fake_gh = directory / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
                "case \"$*\" in\n"
                "  *'/dispatches'*) printf '%s\\n' \"$FAKE_DISPATCH_RESPONSE\" ;;\n"
                "  *'/actions/runs/456'*) printf '%s\\n' \"$FAKE_INVENTORY_RUN_JSON\" ;;\n"
                "  *'/git/ref/heads/prod/release-inventory-123'*) echo \"${FAKE_REMOTE_SHA:-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}\" ;;\n"
                "esac\n",
                encoding="ascii",
            )
            fake_gh.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "GH_CALLS": str(calls),
                    "GH_TOKEN": "ci-only",
                    "GITHUB_REF": "refs/heads/main",
                    "GITHUB_RUN_ID": "123",
                    "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_SHA": "a" * 40,
                    "GITHUB_REPOSITORY": "test/finance",
                    "PYTHON_BIN": sys.executable.replace("\\", "/"),
                    "PATH": str(directory) + os.pathsep + env.get("PATH", ""),
                }
            )
            env["FAKE_DISPATCH_RESPONSE"] = json.dumps({"workflow_run_id": 456})
            env["FAKE_INVENTORY_RUN_JSON"] = json.dumps({
                "id": 456, "event": "workflow_dispatch",
                "head_branch": "prod/release-inventory-123", "head_sha": "a" * 40,
                "actor": {"login": "github-actions[bot]"},
                "display_title": "finance-inventory-inventory-123",
                "run_attempt": 1, "status": "completed", "conclusion": "success",
            })
            result = subprocess.run(
                [bash(), str(OPS / "bootstrap.sh")],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = calls.read_text(encoding="ascii")
            self.assertIn("-X POST repos/test/finance/git/refs", text)
            self.assertIn("-X POST repos/test/finance/actions/workflows/finance-prod-readonly-inventory.yml/dispatches", text)
            self.assertIn("-X DELETE repos/test/finance/git/refs/heads/prod/release-inventory-123", text)
            self.assertNotIn("/runs?branch=", text)

            calls.write_text("", encoding="ascii")
            env["FAKE_REMOTE_SHA"] = "b" * 40
            rejected = subprocess.run(
                [bash(), str(OPS / "bootstrap.sh")],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn("-X DELETE", calls.read_text(encoding="ascii"))

            for response in ("", "{}", '{"workflow_run_id":"456"}', '{"workflow_run_id":0}',
                             '{"workflow_run_id":[456,789]}',
                             '{"workflow_run_id":456,"workflow_run_id":789}'):
                with self.subTest(response=response):
                    calls.write_text("", encoding="ascii")
                    env["FAKE_REMOTE_SHA"] = "a" * 40
                    env["FAKE_DISPATCH_RESPONSE"] = response
                    rejected = subprocess.run(
                        [bash(), str(OPS / "bootstrap.sh")], env=env,
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertNotIn("-X DELETE", calls.read_text(encoding="ascii"))

            calls.write_text("", encoding="ascii")
            env["FAKE_DISPATCH_RESPONSE"] = json.dumps({"workflow_run_id": 456})
            bad = json.loads(env["FAKE_INVENTORY_RUN_JSON"])
            bad["actor"] = {"login": "foreign-user"}
            env["FAKE_INVENTORY_RUN_JSON"] = json.dumps(bad)
            rejected = subprocess.run(
                [bash(), str(OPS / "bootstrap.sh")], env=env,
                capture_output=True, text=True, timeout=15,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn("-X DELETE", calls.read_text(encoding="ascii"))


if __name__ == "__main__":
    unittest.main()
