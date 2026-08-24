from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_WORKFLOW = REPO_ROOT / ".github/workflows/finance-hexcore-prod-deploy.yml"
ROLLBACK_WORKFLOW = REPO_ROOT / ".github/workflows/finance-prod-rollback.yml"
RUNBOOK = REPO_ROOT / "docs/production/finance-cicd-runbook.md"
PREFLIGHT = REPO_ROOT / "docs/production/finance-release-preflight-checklist.md"


def _job(workflow: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z0-9-]+:\n|\Z)",
        workflow,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing workflow job: {name}"
    return match.group("body")


def test_production_jobs_share_both_package_gates_and_host_preflight() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    package_gate = _job(workflow, "production-package-gate")
    host_preflight = _job(workflow, "host-preflight")
    backend = _job(workflow, "deploy-backend")
    frontend = _job(workflow, "deploy-frontend")

    for dependency in ("frontend-ci-package", "backend-ci-package"):
        assert f"- {dependency}" in package_gate
        assert f"- {dependency}" in host_preflight
        assert f"- {dependency}" in backend
        assert f"- {dependency}" in frontend

    assert "if: ${{ always() }}" in package_gate
    assert "production package gate requires success" in package_gate
    assert "- production-package-gate" in host_preflight
    assert "environment: production" in host_preflight
    assert "outputs.production_requested == 'true'" in host_preflight

    for deploy_job in (backend, frontend):
        assert "- production-package-gate" in deploy_job
        assert "- host-preflight" in deploy_job
        assert "needs.production-package-gate.result == 'success'" in deploy_job
        assert "needs.host-preflight.result == 'success'" in deploy_job

    assert "- deploy-backend" in frontend
    assert "needs.deploy-backend.result == 'success'" in frontend


def test_ci_only_dispatch_skips_production_environment_and_host_contact() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    validation = _job(workflow, "validate-prod-inputs")
    host_preflight = _job(workflow, "host-preflight")

    assert 'production_requested="false"' in validation
    assert "outputs.production_requested == 'true'" in host_preflight
    assert "environment: production" not in _job(workflow, "frontend-ci-package")
    assert "environment: production" not in _job(workflow, "backend-ci-package")
    assert "environment: production" not in _job(workflow, "production-package-gate")


def test_incident_qa_credential_rotation_is_isolated_and_fail_closed() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    validation = _job(workflow, "validate-prod-inputs")
    rotation = _job(workflow, "rotate-production-qa-credential")

    assert "github.event_name == 'workflow_dispatch'" in rotation
    assert "inputs.rotate_production_qa_credential == 'true'" in rotation
    assert "environment: production" in rotation
    assert "confirm_qa_credential_rotation must be" in rotation
    assert "all deploy, migration, and restart flags to be false" in rotation
    assert "prod/release-security-incident-qa-rotation-" in rotation
    assert "FINANCE_ACTOR" in rotation
    assert "FINANCE_REPOSITORY_OWNER" in rotation
    assert "secrets.FINANCE_QA_EMAIL" in rotation
    assert "secrets.FINANCE_QA_PASSWORD" in rotation
    assert 'chmod 600 "${local_payload}"' in rotation
    assert "--rotate-password" in rotation
    assert "--confirm-production" in rotation
    assert 'rm -f "${FINANCE_ROTATION_PAYLOAD}"' in rotation
    assert '"deploy_performed": False' in rotation
    assert '"migration_performed": False' in rotation
    assert '"backend_restart_performed": False' in rotation

    for forbidden in (
        "deploy-backend:",
        "deploy-frontend:",
        "alembic upgrade",
        "systemctl restart",
        "FINANCE_QA_PASSWORD}'",
    ):
        assert forbidden not in rotation

    assert "prod/release-security-incident-qa-rotation-" in validation
    assert 'deploy_mode="security_incident_qa_rotation"' in validation
    for assignment in (
        'deploy_frontend="false"',
        'deploy_backend="false"',
        'run_migrations="false"',
        'restart_backend="false"',
    ):
        assert assignment in validation


def test_host_preflight_contract_is_read_only_and_complete() -> None:
    host_preflight = _job(DEPLOY_WORKFLOW.read_text(encoding="utf-8"), "host-preflight")

    for required in (
        'test -L "${frontend_current}"',
        'test -L "${backend_current}"',
        "systemctl is-active --quiet",
        'service_wiring="${service_exec_start}',
        "command -v pg_dump",
        'test -w "${FINANCE_DB_BACKUP_DIR}"',
        "FINANCE_DB_BACKUP_MIN_FREE_KB",
        "alembic -c alembic.ini current",
        "script.iterate_revisions(target, live)",
        "frontend_current_release_id",
        "backend_current_release_id",
        "host-preflight-sanitized.txt",
    ):
        assert required in host_preflight

    for forbidden in ("pg_dump --format", "alembic upgrade", "systemctl restart", "ln -sfn"):
        assert forbidden not in host_preflight


def test_release_trigger_backup_path_and_rollback_docs_are_consistent() -> None:
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    rollback = ROLLBACK_WORKFLOW.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")

    assert '- "prod/release-*"' in deploy
    assert 'FINANCE_DB_BACKUP_DIR: /opt/finance/backups/postgres' in deploy
    assert "/var/backups/finance" not in preflight
    assert "/opt/finance/backups/postgres" in preflight

    assert "current_release_confirmation:" in rollback
    assert "db_rollback_approved:" in rollback
    assert 'default: false' in rollback
    assert 'if [ "${db_rollback_approved}" = "true" ]' in rollback
    assert "`current_release_confirmation=" in runbook
    assert "`db_rollback_approved=false`" in runbook
    assert "release-branch push, migrations and backend restart are automatic" in runbook
