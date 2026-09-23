from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from validate_output import HASH_FIELDS, NUMBER_FIELDS, parse


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORKFLOW = ROOT / ".github/workflows/finance-native-footprint.yml"


def bash() -> str:
    if os.name == "nt":
        return r"C:\Program Files\Git\bin\bash.exe"
    return shutil.which("bash") or "bash"


class FootprintContractTests(unittest.TestCase):
    def valid_data(self) -> bytes:
        values = {
            "schema": "finance_native_footprint_v1",
            "feature_sha": "a" * 40,
            **{name: "b" * 64 for name in HASH_FIELDS},
            "node_version": "24.21.0",
            "npm_version": "11.19.0",
            "sampler_interval_ms": "200",
            **{name: "1" for name in NUMBER_FIELDS},
            "baseline_available_bytes": "100",
            "minimum_sampled_available_bytes": "70",
            "observed_peak_disk_bytes": "30",
            "baseline_available_inodes": "100",
            "minimum_sampled_available_inodes": "90",
            "observed_peak_inodes": "10",
        }
        return "".join(f"{key}={value}\n" for key, value in values.items()).encode()

    def test_fixed_evidence_contract(self) -> None:
        valid = self.valid_data()
        self.assertEqual(parse(valid, "a" * 40)["observed_peak_disk_bytes"], "30")
        for bad in (
            valid + b"secret=value\n",
            valid + b"feature_sha=" + b"a" * 40 + b"\n",
            valid.replace(b"schema=finance_native_footprint_v1\n", b""),
            valid.replace(b"node_version=24.21.0", b"node_version=latest"),
            valid.replace(b"observed_peak_disk_bytes=30", b"observed_peak_disk_bytes=31"),
            valid.replace(b"n8n_stage_bytes=1", b"n8n_stage_bytes=/private/path"),
            valid.replace(b"npm_version=11.19.0", b"npm_version=11.19.0;id"),
            valid.replace(b"\n", b"\r\n"),
        ):
            with self.subTest(bad=bad[-60:]), self.assertRaises(ValueError):
                parse(bad, "a" * 40)
        with self.assertRaises(ValueError):
            parse(valid, "c" * 40)

    def test_pr_verifies_exact_feature_n8n_lock(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        steps = workflow["jobs"]["verify"]["steps"]
        feature_checkout = next(step for step in steps if step.get("with", {}).get("path") == "feature")
        self.assertEqual(feature_checkout["with"]["ref"], "76363ca73756d4c279a115c48c29b53bf10ecef2")
        self.assertEqual(feature_checkout["with"]["persist-credentials"], "false")
        check = steps[-1]["run"]
        self.assertIn("feature/ops/finance-release/native-n8n", check)
        self.assertIn("'2.39.8'", check)
        self.assertIn("npm ci --omit=dev", check)
        self.assertNotIn("--dry-run", check)
        self.assertNotIn("--ignore-scripts", check)

    def test_manual_run_has_no_production_boundary_or_secret_passthrough(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertIn("pull_request", workflow["on"])
        self.assertIn("workflow_dispatch", workflow["on"])
        self.assertNotIn("push", workflow["on"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["measure"]
        self.assertNotIn("environment", job)
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertIn("refs/heads/main", job["if"])
        self.assertIn("github.actor == 'DmtrGoltsev'", job["if"])
        guard, trusted_checkout, feature_checkout = job["steps"][:3]
        self.assertIn("codex/investment-recommendations-ci-20260923", guard["run"])
        self.assertIn('[[ "$branch_sha" == "$FEATURE_SHA" ]]', guard["run"])
        self.assertEqual(trusted_checkout["with"]["persist-credentials"], "false")
        self.assertEqual(feature_checkout["with"]["persist-credentials"], "false")
        self.assertEqual(feature_checkout["with"]["ref"], "${{ inputs.feature_sha }}")
        self.assertIn("validate_output.py", job["steps"][3]["run"])
        self.assertNotIn("secrets.", WORKFLOW.read_text(encoding="utf-8"))
        for forbidden in ("ssh ", "scp ", "docker ", "sudo ", "production:", "deploy"):
            self.assertNotIn(forbidden, WORKFLOW.read_text(encoding="utf-8").lower())

    def test_shell_and_measurement_scope(self) -> None:
        script = (HERE / "measure.sh").read_text(encoding="utf-8")
        result = subprocess.run([bash(), "-n", str(HERE / "measure.sh")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for required in ("df -B1 --output=avail", "df --output=iavail", "sleep 0.2", "npm ci", "cp -a", "sha256sum --check", "ops/finance-release/native-n8n"):
            self.assertIn(required, script)
        for forbidden in (".env", "printenv", "docker ", "ssh ", "sudo ", "pg_dump", "git push"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
