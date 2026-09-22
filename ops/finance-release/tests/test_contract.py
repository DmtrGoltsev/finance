from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import callback_proxy
import contract
import host_release


def approved(now: dt.datetime) -> dict:
    return {
        "inventory_run_id": "123456789", "captured_at_utc": (now - dt.timedelta(hours=1)).isoformat(),
        "approved_at_utc": (now - dt.timedelta(minutes=30)).isoformat(),
        "approval_ticket": "FIN-123", "host_name": "finance-host", "os_id": "ubuntu",
        "os_version_id": "24.04", "architecture": "x86_64", "min_cpus": 2,
        "min_available_memory_mb": 4096, "min_free_disk_mb": 10240,
        "bridge_name": "finance_delivery_host_bridge", "bridge_subnet": "172.29.240.0/24",
        "bridge_gateway": "172.29.240.1", "callback_port": 18081, "n8n_port": 5680,
        "docker_packages": {name: "1.2.3-1~ubuntu.24.04~noble" for name in contract.PACKAGES},
        "images": {name: f"example/{name}:pinned@sha256:{'a' * 64}" for name in contract.IMAGES},
    }


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 9, 23, 12, tzinfo=dt.timezone.utc)
        self.approval = approved(self.now)

    def validate(self):
        return contract.validate_approval(json.dumps(self.approval).encode(), self.now)

    def test_complete_fresh_approval_is_accepted(self):
        self.assertEqual(self.validate()["bridge_gateway"], "172.29.240.1")

    def test_missing_or_stale_inventory_fails_closed(self):
        del self.approval["inventory_run_id"]
        with self.assertRaisesRegex(contract.ContractError, "fields"):
            self.validate()
        self.approval = approved(self.now)
        self.approval["captured_at_utc"] = (self.now - dt.timedelta(hours=25)).isoformat()
        with self.assertRaisesRegex(contract.ContractError, "older than 24 hours"):
            self.validate()

    def test_floating_image_and_unapproved_network_fail(self):
        self.approval["images"]["n8n"] = "n8nio/n8n:latest"
        with self.assertRaisesRegex(contract.ContractError, "digest-pinned"):
            self.validate()
        self.approval = approved(self.now)
        self.approval["bridge_gateway"] = "172.29.240.2"
        with self.assertRaisesRegex(contract.ContractError, "first usable"):
            self.validate()

    def test_unsupported_os_or_insufficient_approved_resources_fail(self):
        self.approval["os_id"] = "unknown"
        with self.assertRaisesRegex(contract.ContractError, "Ubuntu/Debian"):
            self.validate()
        self.approval = approved(self.now)
        self.approval["min_available_memory_mb"] = 512
        with self.assertRaisesRegex(contract.ContractError, "at least 3072"):
            self.validate()


class CallbackProxyTests(unittest.TestCase):
    def test_callback_path_is_narrow(self):
        valid = "/api/v1/investments/internal/recommendation-jobs/11111111-1111-4111-8111-111111111111/callback"
        self.assertIsNotNone(callback_proxy.CALLBACK_PATH.fullmatch(valid))
        for path in ("/api/v1/accounts", "/health", valid + "/other", valid + "?x=1"):
            self.assertIsNone(callback_proxy.CALLBACK_PATH.fullmatch(path))

    def test_proxy_rejects_unsigned_requests_before_upstream(self):
        import ipaddress
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        server = ThreadingHTTPServer(("127.0.0.1", 0), callback_proxy.handler_for(ipaddress.ip_network("127.0.0.0/8")))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            path = "/api/v1/investments/internal/recommendation-jobs/11111111-1111-4111-8111-111111111111/callback"
            request = Request(f"http://127.0.0.1:{server.server_port}{path}", data=b"{}", method="POST")
            with self.assertRaises(HTTPError) as error:
                urlopen(request, timeout=2)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class HostReleaseTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Windows does not expose POSIX file modes")
    def test_generated_secrets_are_persisted_once_and_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.env"
            with patch.object(host_release, "GENERATED", path):
                first = host_release.generated_secrets()
                second = host_release.generated_secrets()
            self.assertEqual(first, second)
            self.assertEqual(set(first), set(host_release.GENERATED_KEYS))
            self.assertEqual(len(set(first.values())), len(first))
            self.assertTrue(all(len(value) == 64 for value in first.values()))

    def test_compose_environment_uses_only_approved_images_and_bridge(self):
        approval = approved(dt.datetime.now(dt.timezone.utc))
        generated = {key: "a" * 64 for key in host_release.GENERATED_KEYS}
        env = host_release.compose_env(approval, {"DEEPSEEK_API_KEY": "ci-only"}, generated, "release-test")
        self.assertEqual(env["FINANCE_N8N_IMAGE"], approval["images"]["n8n"])
        self.assertEqual(env["FINANCE_POSTGRES_IMAGE"], approval["images"]["postgres"])
        self.assertEqual(env["FINANCE_DELIVERY_BRIDGE_GATEWAY"], approval["bridge_gateway"])

    def test_existing_release_rejects_any_changed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "base"
            source = Path(temp) / "incoming"
            for name in ("finance-n8n", "finance-release"):
                (source / "ops" / name).mkdir(parents=True)
            (source / "ops/finance-n8n/compose.yml").write_text("services: {}\n", encoding="utf-8")
            (source / "ops/finance-n8n/workflow.json").write_text("{}", encoding="utf-8")
            (source / "ops/finance-release/host_release.py").write_text("pass\n", encoding="utf-8")
            approval = approved(dt.datetime.now(dt.timezone.utc))
            with patch.object(host_release, "BASE", base):
                host_release._stage_source(source, "r1", approval)
                host_release._stage_source(source, "r1", approval)
                (source / "ops/finance-n8n/workflow.json").write_text('{"changed":true}', encoding="utf-8")
                with self.assertRaisesRegex(contract.ContractError, "content differs"):
                    host_release._stage_source(source, "r1", approval)

    def test_e2e_creates_idempotent_job_and_reads_report(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        snapshot_id = "22222222-2222-4222-8222-222222222222"
        calls = []

        class Response(io.BytesIO):
            def __init__(self, status, data):
                super().__init__(json.dumps({"data": data}).encode())
                self.status = status

        def respond(request, timeout):
            calls.append(request)
            if request.method == "POST":
                payload = json.loads(request.data)
                self.assertEqual(payload["snapshotIds"], [snapshot_id])
                self.assertLessEqual(len(payload["idempotencyKey"]), 128)
                return Response(202, {"id": job_id})
            if request.full_url.endswith("/report"):
                return Response(200, {"jobId": job_id})
            return Response(200, {"status": "ready"})

        with tempfile.TemporaryDirectory() as temp:
            token = Path(temp) / "token"
            token.write_text("test-token", encoding="utf-8")
            external = {"FINANCE_E2E_BEARER_TOKEN_FILE": str(token),
                        "FINANCE_E2E_SNAPSHOT_ID": snapshot_id}
            with patch.object(host_release.urllib.request, "urlopen", side_effect=respond):
                host_release._e2e(external, "r" * 128)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call.get_header("Authorization") == "Bearer test-token" for call in calls))


class WorkflowTests(unittest.TestCase):
    def test_release_push_keeps_pre_host_hold(self):
        workflow = (REPO / ".github/workflows/finance-hexcore-prod-deploy.yml").read_text(encoding="utf-8")
        self.assertIn('deploy_mode="release_push"', workflow)
        self.assertIn('production_requested="true"', workflow)
        self.assertIn("DELIVERY_HOST_NATIVE_CAPACITY_UNVERIFIED", workflow)
        gate = workflow.split("  production-package-gate:", 1)[1].split("  host-preflight:", 1)[0]
        self.assertIn('if [ "${FINANCE_PRODUCTION_REQUESTED}" = "true" ]; then', gate)
        self.assertIn('echo "::error::DELIVERY_HOST_NATIVE_CAPACITY_UNVERIFIED', gate)
        self.assertIn('exit 1\n          else', gate)
        self.assertNotIn("FINANCE_DELIVERY_CONTRACT_APPROVED", gate)
        self.assertIn("- production-package-gate", workflow.split("  host-preflight:", 1)[1].split("  deploy-frontend:", 1)[0])

    def test_every_host_job_is_downstream_of_pre_host_gate(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/finance-hexcore-prod-deploy.yml").read_text(encoding="utf-8"))
        jobs = workflow["jobs"]

        def ancestors(name):
            dependencies = jobs[name].get("needs", [])
            if isinstance(dependencies, str):
                dependencies = [dependencies]
            return set(dependencies).union(*(ancestors(dependency) for dependency in dependencies))

        for name, job in jobs.items():
            scripts = "\n".join(str(step.get("run", "")) for step in job.get("steps", []))
            if re.search(r"\b(?:ssh|scp)\b", scripts):
                self.assertIn("production-package-gate", ancestors(name), name)
        self.assertIn("delivery-ci-package", ancestors("production-package-gate"))
        self.assertIn("deploy-delivery-stage", ancestors("deploy-backend"))
        self.assertIn("activate-delivery", ancestors("deploy-frontend"))
        self.assertIn("needs.activate-delivery.result == 'success'", jobs["deploy-frontend"]["if"])


if __name__ == "__main__":
    unittest.main()
