"""Loader skeleton for owner-member-other-invited-former-v1 fixtures.

This module deliberately stays runner-neutral. It validates manifest shape,
allocates deterministic synthetic ids, and builds sanitized metadata for future
test runners. It does not access databases, production app modules, generated
clients, network services, or real secrets.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sanitization import assert_safe_evidence_keys


FIXTURE_SET = "owner-member-other-invited-former-v1"
EVIDENCE_VERSION = "wave-2-fixture-evidence-v1"
NORMALIZED_TIMESTAMP = "NORMALIZED_TIMESTAMP"
TTR_CONTRACT_GRAPH_FILENAME = "canonical-uuid-graph.json"
TTR_GOLDEN_FILES = {
    "visibility": "goldens/visibility-expected.json",
    "reports": "goldens/report-expected.json",
    "transfer_denials": "goldens/transfer-denials-expected.json",
}

_ID_NAMESPACE = uuid.UUID("6d629442-78d6-4f2b-8b98-28c5b12c840d")
_LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CANONICAL_ACTORS = {"owner_a", "member_b", "other_c", "invited_ab", "former_ab"}
_REQUIRED_TOP_LEVEL_KEYS = {
    "artifactVersion",
    "fixtureSet",
    "sourceDocuments",
    "safety",
    "actorLabels",
    "households",
    "memberships",
    "accounts",
    "categories",
    "transactions",
    "transfers",
    "reports",
    "sessions",
    "invites",
    "privacy",
    "cache",
    "exports",
    "loader",
    "evidenceMapping",
}
_LIST_SECTIONS = {
    "sourceDocuments",
    "actorLabels",
    "households",
    "memberships",
    "accounts",
    "categories",
    "transactions",
    "sessions",
    "invites",
    "cache",
    "exports",
}
_OBJECT_SECTIONS = {"safety", "transfers", "reports", "privacy", "loader", "evidenceMapping"}
_EVIDENCE_BUCKETS = {
    "api",
    "authz",
    "reports",
    "transfers",
    "privacy",
    "client",
    "security",
    "backups",
    "dependencies",
}


class FixtureValidationError(ValueError):
    """Raised when the fixture manifest fails lightweight validation."""


class FixtureContractError(ValueError):
    """Raised when W3 TTR fixture contract files are internally inconsistent."""


@dataclass(frozen=True)
class FixtureBundle:
    """Sanitized fixture loader outputs for future runner integration."""

    sanitizedLabelToIdMap: dict[str, Any]
    fixtureGraphSummary: dict[str, Any]
    evidenceManifest: dict[str, Any]
    redactionScanSummary: dict[str, Any]
    validationWarnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sanitizedLabelToIdMap": self.sanitizedLabelToIdMap,
            "fixtureGraphSummary": self.fixtureGraphSummary,
            "evidenceManifest": self.evidenceManifest,
            "redactionScanSummary": self.redactionScanSummary,
            "validationWarnings": list(self.validationWarnings),
        }


@dataclass(frozen=True)
class TtrFixtureContracts:
    """Validated W3 transactions/transfers/reports fixture contract bundle."""

    canonicalGraph: dict[str, Any]
    goldenExpectations: dict[str, dict[str, Any]]
    contractSummary: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "contractSummary": self.contractSummary,
            "goldenExpectationGroups": sorted(self.goldenExpectations),
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a fixture manifest JSON document."""

    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        loaded = json.load(manifest_file)
    if not isinstance(loaded, dict):
        raise FixtureValidationError("Manifest root must be a JSON object")
    return loaded


def load_json_document(path: str | Path) -> dict[str, Any]:
    """Load a runner-neutral fixture JSON document."""

    document_path = Path(path)
    with document_path.open("r", encoding="utf-8") as document_file:
        loaded = json.load(document_file)
    if not isinstance(loaded, dict):
        raise FixtureContractError(f"{document_path} root must be a JSON object")
    return loaded


def load_ttr_fixture_contracts(fixture_root: str | Path) -> TtrFixtureContracts:
    """Load and validate W3 TTR UUID graph and golden expectation files."""

    root = Path(fixture_root)
    canonical_graph = load_json_document(root / TTR_CONTRACT_GRAPH_FILENAME)
    golden_docs = {
        group: load_json_document(root / relative_path)
        for group, relative_path in TTR_GOLDEN_FILES.items()
    }

    validate_canonical_uuid_graph(canonical_graph)
    validate_golden_expectations(golden_docs, canonical_graph)

    summary = _build_ttr_contract_summary(canonical_graph, golden_docs)
    assert_safe_evidence_keys(summary)

    return TtrFixtureContracts(
        canonicalGraph=canonical_graph,
        goldenExpectations=golden_docs,
        contractSummary=summary,
    )


def validate_canonical_uuid_graph(graph: Mapping[str, Any]) -> None:
    """Validate the W3 TTR canonical UUID graph without runtime imports."""

    errors: list[str] = []

    if graph.get("fixtureSet") != FIXTURE_SET:
        errors.append(f"fixtureSet must be {FIXTURE_SET!r}")

    safety = graph.get("safety")
    if not isinstance(safety, Mapping):
        errors.append("safety must be an object")
    else:
        if safety.get("syntheticOnly") is not True:
            errors.append("safety.syntheticOnly must be true")
        if safety.get("containsConcreteFinancialValues") is not False:
            errors.append("safety.containsConcreteFinancialValues must be false")
        if safety.get("containsRealPersonalData") is not False:
            errors.append("safety.containsRealPersonalData must be false")

    actors = _labels_for_section(graph, "actors")
    missing_actors = sorted(_CANONICAL_ACTORS.difference(actors))
    if missing_actors:
        errors.append(f"canonical graph missing actors: {', '.join(missing_actors)}")

    uuid_errors = _validate_unique_canonical_uuids(graph)
    errors.extend(uuid_errors)

    labels = _labels_by_section(graph)
    all_labels = {label for section_labels in labels.values() for label in section_labels}
    for required_label in {
        "acc_invited_personal",
        "acc_former_personal",
        "txn_invited_personal_may",
        "txn_former_personal_may",
        "trf_denied_missing_counterparty",
        "rep_former_ab_denied",
    }:
        if required_label not in all_labels:
            errors.append(f"canonical graph missing required W3 label: {required_label}")

    contracts = graph.get("contracts")
    if not isinstance(contracts, Mapping):
        errors.append("contracts must be an object")
    else:
        if contracts.get("sourceType") != ["manual"]:
            errors.append("contracts.sourceType must be ['manual']")
        if contracts.get("reportModes") != [
            "personal",
            "shared_family_report",
            "combined_viewer_overview",
        ]:
            errors.append("contracts.reportModes must contain only supported MVP report modes")
        if contracts.get("transferScopes") != [
            "personal_same_owner",
            "household_same_household",
        ]:
            errors.append("contracts.transferScopes must contain only same-scope values")
        forbidden_routes = contracts.get("forbiddenRouteFamilies")
        if not isinstance(forbidden_routes, list) or "/api/v1/transfers" not in forbidden_routes:
            errors.append("contracts.forbiddenRouteFamilies must include /api/v1/transfers")

    for item in graph.get("plannedTransactions", []):
        if not isinstance(item, Mapping):
            continue
        if item.get("sourceType") != "manual":
            errors.append(f"{item.get('label', '<unknown>')} sourceType must be manual")

    if errors:
        raise FixtureContractError("; ".join(errors))


def validate_golden_expectations(
    golden_docs: Mapping[str, Mapping[str, Any]],
    canonical_graph: Mapping[str, Any],
) -> None:
    """Validate W3 golden expectation documents against the canonical graph."""

    errors: list[str] = []
    labels = _labels_by_section(canonical_graph)
    graph_labels = {label for section_labels in labels.values() for label in section_labels}
    expected_groups = set(TTR_GOLDEN_FILES)
    missing_groups = sorted(expected_groups.difference(golden_docs.keys()))
    if missing_groups:
        errors.append(f"missing golden groups: {', '.join(missing_groups)}")

    for group, document in golden_docs.items():
        if document.get("fixtureSet") != FIXTURE_SET:
            errors.append(f"{group}.fixtureSet must be {FIXTURE_SET!r}")
        cases = document.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{group}.cases must be a non-empty array")
            continue
        seen_cases: set[str] = set()
        for case in cases:
            if not isinstance(case, Mapping):
                errors.append(f"{group}.cases contains a non-object case")
                continue
            label = case.get("label")
            if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
                errors.append(f"{group} case has invalid label: {label!r}")
                continue
            if label in seen_cases:
                errors.append(f"{group} duplicate case label: {label}")
            seen_cases.add(label)
            _validate_referenced_labels(group, label, case, graph_labels, errors)

    visibility = golden_docs.get("visibility", {})
    if isinstance(visibility, Mapping):
        forbidden = set(visibility.get("forbiddenResponseFields", []))
        for required in {"hiddenCount", "filteredOutCount", "totalCount"}:
            if required not in forbidden:
                errors.append(f"visibility forbids must include {required}")

    reports = golden_docs.get("reports", {})
    if isinstance(reports, Mapping):
        endpoints = set(reports.get("endpoints", []))
        for endpoint in {
            "/api/v1/reports/summary",
            "/api/v1/reports/category-breakdown",
            "/api/v1/reports/account-balances",
            "/api/v1/reports/cash-flow",
            "/api/v1/reports/transactions",
        }:
            if endpoint not in endpoints:
                errors.append(f"reports endpoints missing {endpoint}")

    transfer_denials = golden_docs.get("transfer_denials", {})
    if isinstance(transfer_denials, Mapping):
        if transfer_denials.get("allowedScopes") != [
            "personal_same_owner",
            "household_same_household",
        ]:
            errors.append("transfer_denials.allowedScopes must be same-scope only")
        case_labels = {
            case.get("label")
            for case in transfer_denials.get("cases", [])
            if isinstance(case, Mapping)
        }
        for required in {
            "trf_denied_personal_to_shared",
            "trf_denied_shared_to_personal",
            "trf_denied_cross_user_personal",
            "trf_denied_cross_household_shared",
            "trf_denied_invited_shared",
            "trf_denied_former_shared_restore",
            "trf_denied_missing_counterparty",
        }:
            if required not in case_labels:
                errors.append(f"transfer_denials cases missing {required}")

    if errors:
        raise FixtureContractError("; ".join(errors))


def validate_manifest_shape(manifest: Mapping[str, Any]) -> list[str]:
    """Validate the manifest at a lightweight shape level.

    TODO(full-validation): wire JSON Schema validation if a future runner owns a
    ``jsonschema`` dependency. This skeleton must keep working without it.
    """

    errors: list[str] = []
    warnings: list[str] = []

    if importlib.util.find_spec("jsonschema") is None:
        warnings.append(
            "TODO(full-validation): jsonschema is absent; only lightweight shape validation ran."
        )

    missing = sorted(_REQUIRED_TOP_LEVEL_KEYS.difference(manifest.keys()))
    if missing:
        errors.append(f"Missing required top-level keys: {', '.join(missing)}")

    if manifest.get("artifactVersion") != FIXTURE_SET:
        errors.append(f"artifactVersion must be {FIXTURE_SET!r}")
    if manifest.get("fixtureSet") != FIXTURE_SET:
        errors.append(f"fixtureSet must be {FIXTURE_SET!r}")

    for section in sorted(_LIST_SECTIONS):
        if section in manifest and not isinstance(manifest[section], list):
            errors.append(f"{section} must be an array")

    for section in sorted(_OBJECT_SECTIONS):
        if section in manifest and not isinstance(manifest[section], Mapping):
            errors.append(f"{section} must be an object")

    _validate_safety(manifest.get("safety"), errors)
    _validate_actor_labels(manifest.get("actorLabels"), errors)
    _validate_label_objects(manifest, errors)
    _validate_loader_section(manifest.get("loader"), errors)
    _validate_evidence_mapping(manifest.get("evidenceMapping"), errors)

    if errors:
        raise FixtureValidationError("; ".join(errors))
    return warnings


def deterministic_synthetic_id(label: str, *, fixture_set: str = FIXTURE_SET) -> str:
    """Return a stable opaque id derived from a fixture label."""

    if not _LABEL_RE.fullmatch(label):
        raise FixtureValidationError(f"Invalid fixture label: {label!r}")
    stable_uuid = uuid.uuid5(_ID_NAMESPACE, f"{fixture_set}:{label}")
    checksum = hashlib.sha256(f"{fixture_set}:{label}".encode("utf-8")).hexdigest()[:8]
    return f"ffx_{stable_uuid.hex[:20]}_{checksum}"


def build_fixture_bundle(manifest: Mapping[str, Any]) -> FixtureBundle:
    """Build sanitized label/id and evidence skeleton outputs."""

    warnings = validate_manifest_shape(manifest)
    labels = _collect_label_records(manifest)
    label_to_id = {
        label: deterministic_synthetic_id(label)
        for label in sorted(record["label"] for record in labels)
    }

    label_map = {
        "artifactVersion": FIXTURE_SET,
        "fixtureSet": FIXTURE_SET,
        "idStrategy": "uuid5_sha256_label_only",
        "labels": {
            label: {
                "syntheticId": synthetic_id,
                "sourcePath": _source_path_for_label(labels, label),
            }
            for label, synthetic_id in label_to_id.items()
        },
    }

    graph_summary = _build_graph_summary(manifest, labels)
    evidence_manifest = _build_evidence_manifest(manifest)
    redaction_summary = {
        "status": "pass",
        "scanner": "finance_fixtures.sanitization.assert_safe_evidence_keys",
        "checkedOutputs": [
            "sanitizedLabelToIdMap",
            "fixtureGraphSummary",
            "evidenceManifest",
        ],
        "forbiddenKeyFamilies": [
            "tokens",
            "token_hashes",
            "passwords",
            "raw_bodies",
            "amounts_in_logs",
            "account_names_in_logs",
            "category_names_in_logs",
            "secrets",
        ],
    }

    for output in (label_map, graph_summary, evidence_manifest, redaction_summary):
        assert_safe_evidence_keys(output)

    return FixtureBundle(
        sanitizedLabelToIdMap=label_map,
        fixtureGraphSummary=graph_summary,
        evidenceManifest=evidence_manifest,
        redactionScanSummary=redaction_summary,
        validationWarnings=warnings,
    )


def _validate_safety(section: Any, errors: list[str]) -> None:
    if not isinstance(section, Mapping):
        return
    if section.get("syntheticOnly") is not True:
        errors.append("safety.syntheticOnly must be true")
    forbidden = section.get("forbiddenValues")
    if not isinstance(forbidden, list):
        errors.append("safety.forbiddenValues must be an array")
        return
    required_forbidden = {
        "tokens",
        "token_hashes",
        "plaintext_passwords",
        "secrets",
        "raw_financial_payloads",
        "amounts_in_logs",
        "account_names_in_logs",
        "category_names_in_logs",
        "production_config",
    }
    missing = sorted(required_forbidden.difference(forbidden))
    if missing:
        errors.append(f"safety.forbiddenValues missing: {', '.join(missing)}")


def _validate_actor_labels(section: Any, errors: list[str]) -> None:
    if not isinstance(section, list):
        return
    actor_labels = {
        item.get("label")
        for item in section
        if isinstance(item, Mapping) and isinstance(item.get("label"), str)
    }
    missing = sorted(_CANONICAL_ACTORS.difference(actor_labels))
    if missing:
        errors.append(f"actorLabels missing canonical actors: {', '.join(missing)}")


def _validate_label_objects(manifest: Mapping[str, Any], errors: list[str]) -> None:
    labels = _collect_label_records(manifest)
    seen: dict[str, str] = {}
    for record in labels:
        label = record["label"]
        if not _LABEL_RE.fullmatch(label):
            errors.append(f"Invalid label {label!r} at {record['sourcePath']}")
        if label in seen:
            errors.append(
                f"Duplicate label {label!r} at {seen[label]} and {record['sourcePath']}"
            )
        seen[label] = record["sourcePath"]


def _validate_loader_section(section: Any, errors: list[str]) -> None:
    if not isinstance(section, Mapping):
        return
    if section.get("runnerNeutral") is not True:
        errors.append("loader.runnerNeutral must be true")
    phases = section.get("phases")
    if not isinstance(phases, list) or "validate_manifest" not in phases:
        errors.append("loader.phases must include validate_manifest")
    outputs = section.get("outputs")
    if not isinstance(outputs, list):
        errors.append("loader.outputs must be an array")
        return
    for required_output in (
        "sanitizedLabelToIdMap",
        "evidenceManifest",
        "redactionScanSummary",
    ):
        if required_output not in outputs:
            errors.append(f"loader.outputs missing {required_output}")


def _validate_evidence_mapping(section: Any, errors: list[str]) -> None:
    if not isinstance(section, Mapping):
        return
    if section.get("root") != "artifacts/evidence":
        errors.append("evidenceMapping.root must be artifacts/evidence")
    buckets = section.get("buckets")
    if not isinstance(buckets, Mapping):
        errors.append("evidenceMapping.buckets must be an object")
        return
    missing = sorted(_EVIDENCE_BUCKETS.difference(buckets.keys()))
    if missing:
        errors.append(f"evidenceMapping.buckets missing: {', '.join(missing)}")


def _collect_label_records(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            label = value.get("label")
            if isinstance(label, str):
                records.append({"label": label, "sourcePath": path})
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(manifest, "$")
    return records


def _source_path_for_label(records: Iterable[Mapping[str, str]], label: str) -> str:
    for record in records:
        if record["label"] == label:
            return record["sourcePath"]
    raise FixtureValidationError(f"Label not collected: {label}")


def _build_graph_summary(
    manifest: Mapping[str, Any], labels: list[dict[str, str]]
) -> dict[str, Any]:
    reports = manifest.get("reports") if isinstance(manifest.get("reports"), Mapping) else {}
    transfers = (
        manifest.get("transfers") if isinstance(manifest.get("transfers"), Mapping) else {}
    )
    privacy = manifest.get("privacy") if isinstance(manifest.get("privacy"), Mapping) else {}

    return {
        "fixtureSet": FIXTURE_SET,
        "syntheticOnly": True,
        "counts": {
            "labels": len(labels),
            "actors": len(manifest.get("actorLabels", [])),
            "households": len(manifest.get("households", [])),
            "memberships": len(manifest.get("memberships", [])),
            "accounts": len(manifest.get("accounts", [])),
            "categories": len(manifest.get("categories", [])),
            "transactions": len(manifest.get("transactions", [])),
            "transfersAllowed": len(transfers.get("allowed", [])),
            "transfersDenied": len(transfers.get("denied", [])),
            "reportPeriods": len(reports.get("periods", [])),
            "reportFixtures": len(reports.get("fixtures", [])),
            "goldens": len(reports.get("goldens", [])),
            "sessions": len(manifest.get("sessions", [])),
            "invites": len(manifest.get("invites", [])),
            "privacyDeleteFixtures": len(privacy.get("deleteFixtures", [])),
            "privacyLeaveFixtures": len(privacy.get("leaveFixtures", [])),
            "cacheFixtures": len(manifest.get("cache", [])),
            "exports": len(manifest.get("exports", [])),
        },
        "canonicalActors": sorted(_CANONICAL_ACTORS),
        "execution": {
            "databaseSeedExecution": "not_implemented",
            "productionImports": "not_used",
            "generatedClients": "not_used",
        },
    }


def _build_evidence_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    evidence_mapping = manifest.get("evidenceMapping", {})
    buckets = {}
    scenario_families: list[str] = []

    if isinstance(evidence_mapping, Mapping):
        raw_buckets = evidence_mapping.get("buckets", {})
        if isinstance(raw_buckets, Mapping):
            buckets = {
                f"artifacts/evidence/{name}": {"status": "not_run", "items": []}
                for name in sorted(raw_buckets.keys())
            }
        raw_families = evidence_mapping.get("scenarioFamilies", [])
        if isinstance(raw_families, list):
            scenario_families = [str(item) for item in raw_families]

    actors = []
    for item in manifest.get("actorLabels", []):
        if isinstance(item, Mapping) and isinstance(item.get("label"), str):
            actors.append(item["label"])

    return {
        "artifactVersion": EVIDENCE_VERSION,
        "generatedAt": NORMALIZED_TIMESTAMP,
        "gitOrBuildRef": "ADR_OR_CI_VALUE_WHEN_AVAILABLE",
        "runner": "ADR_PENDING",
        "fixtureSet": FIXTURE_SET,
        "actors": actors,
        "scenarioFamilies": scenario_families,
        "result": "not_run",
        "blockingGaps": [],
        "buckets": buckets,
    }


def _labels_for_section(graph: Mapping[str, Any], section: str) -> set[str]:
    raw_section = graph.get(section, [])
    if not isinstance(raw_section, list):
        return set()
    return {
        item["label"]
        for item in raw_section
        if isinstance(item, Mapping) and isinstance(item.get("label"), str)
    }


def _labels_by_section(graph: Mapping[str, Any]) -> dict[str, set[str]]:
    return {
        section: _labels_for_section(graph, section)
        for section in (
            "actors",
            "households",
            "memberships",
            "accounts",
            "categories",
            "plannedTransactions",
            "plannedTransfers",
            "plannedReports",
            "periods",
        )
    }


def _validate_unique_canonical_uuids(graph: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            canonical_id = value.get("canonicalId")
            label = value.get("label", path)
            if canonical_id is not None:
                if not isinstance(canonical_id, str):
                    errors.append(f"{path}.canonicalId must be a string")
                else:
                    try:
                        parsed = uuid.UUID(canonical_id)
                    except ValueError:
                        errors.append(f"{path}.canonicalId is not a UUID")
                    else:
                        normalized = str(parsed)
                        previous = seen.get(normalized)
                        if previous is not None:
                            errors.append(
                                f"duplicate canonicalId {normalized} for {previous} and {label}"
                            )
                        seen[normalized] = str(label)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(graph, "$")
    if not seen:
        errors.append("canonical graph must contain canonicalId values")
    return errors


def _validate_referenced_labels(
    group: str,
    case_label: str,
    case: Mapping[str, Any],
    graph_labels: set[str],
    errors: list[str],
) -> None:
    allowed_external_labels = {"missing_counterparty_account"}
    reference_keys = {
        "allow",
        "deny",
        "expectedIncludedAccounts",
        "mustExclude",
        "sourceAccount",
        "counterpartyAccount",
        "household",
    }

    def check(value: Any, key: str) -> None:
        if isinstance(value, str):
            if value not in graph_labels and value not in allowed_external_labels:
                errors.append(f"{group}.{case_label}.{key} references unknown label {value}")
            return
        if isinstance(value, list):
            for child in value:
                check(child, key)

    for key in reference_keys:
        if key in case:
            check(case[key], key)


def _build_ttr_contract_summary(
    graph: Mapping[str, Any],
    golden_docs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    labels = _labels_by_section(graph)
    contracts = graph.get("contracts") if isinstance(graph.get("contracts"), Mapping) else {}
    return {
        "fixtureSet": FIXTURE_SET,
        "artifactVersion": graph.get("artifactVersion"),
        "syntheticOnly": True,
        "counts": {
            "actors": len(labels["actors"]),
            "households": len(labels["households"]),
            "memberships": len(labels["memberships"]),
            "accounts": len(labels["accounts"]),
            "categories": len(labels["categories"]),
            "plannedTransactions": len(labels["plannedTransactions"]),
            "plannedTransfers": len(labels["plannedTransfers"]),
            "plannedReports": len(labels["plannedReports"]),
            "goldenGroups": len(golden_docs),
            "goldenCases": sum(
                len(document.get("cases", []))
                for document in golden_docs.values()
                if isinstance(document.get("cases"), list)
            ),
        },
        "canonicalActors": sorted(labels["actors"]),
        "contractEnums": {
            "sourceType": list(contracts.get("sourceType", [])),
            "reportModes": list(contracts.get("reportModes", [])),
            "transferScopes": list(contracts.get("transferScopes", [])),
        },
        "runtimeMountState": "not_mounted_until_runtime_worker",
    }
