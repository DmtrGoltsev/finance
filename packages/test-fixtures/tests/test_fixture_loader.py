from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from finance_fixtures import (  # noqa: E402
    FIXTURE_SET,
    FixtureContractError,
    FixtureValidationError,
    SanitizationError,
    assert_safe_evidence_keys,
    build_fixture_bundle,
    deterministic_synthetic_id,
    load_json_document,
    load_manifest,
    load_ttr_fixture_contracts,
    validate_canonical_uuid_graph,
    validate_manifest_shape,
)


MANIFEST_PATH = (
    WORKSPACE_ROOT
    / "qa"
    / "fixtures"
    / "owner-member-other-invited-former-v1"
    / "fixtures.manifest.example.json"
)
FIXTURE_ROOT = MANIFEST_PATH.parent
CANONICAL_GRAPH_PATH = FIXTURE_ROOT / "canonical-uuid-graph.json"


class FixtureLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST_PATH)

    def test_example_manifest_parses_and_validates(self) -> None:
        warnings = validate_manifest_shape(self.manifest)

        self.assertEqual(self.manifest["fixtureSet"], FIXTURE_SET)
        self.assertIsInstance(warnings, list)

    def test_bundle_contains_sanitized_label_map_and_evidence_skeleton(self) -> None:
        bundle = build_fixture_bundle(self.manifest)
        data = bundle.as_dict()

        self.assertIn("owner_a", bundle.sanitizedLabelToIdMap["labels"])
        self.assertIn("acc_ab_cash", bundle.sanitizedLabelToIdMap["labels"])
        self.assertEqual(bundle.evidenceManifest["result"], "not_run")
        self.assertEqual(bundle.evidenceManifest["fixtureSet"], FIXTURE_SET)
        self.assertIn("artifacts/evidence/authz", bundle.evidenceManifest["buckets"])
        self.assertEqual(
            bundle.fixtureGraphSummary["execution"]["databaseSeedExecution"],
            "not_implemented",
        )
        assert_safe_evidence_keys(data)

    def test_synthetic_ids_are_deterministic_and_label_derived(self) -> None:
        first = deterministic_synthetic_id("owner_a")
        second = deterministic_synthetic_id("owner_a")
        other = deterministic_synthetic_id("member_b")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertTrue(first.startswith("ffx_"))

    def test_invalid_manifest_shape_fails_without_jsonschema_dependency(self) -> None:
        invalid = json.loads(json.dumps(self.manifest))
        invalid.pop("actorLabels")

        with self.assertRaises(FixtureValidationError):
            validate_manifest_shape(invalid)

    def test_sanitizer_rejects_forbidden_log_and_evidence_keys(self) -> None:
        forbidden_examples = [
            {"tokens": []},
            {"token_hashes": []},
            {"passwords": []},
            {"rawRequestBodies": []},
            {"amounts": []},
            {"accountNames": []},
            {"categoryNames": []},
            {"secrets": []},
        ]

        for payload in forbidden_examples:
            with self.subTest(payload=payload):
                with self.assertRaises(SanitizationError):
                    assert_safe_evidence_keys(payload)

    def test_w3_ttr_canonical_uuid_graph_validates_contract_boundaries(self) -> None:
        graph = load_json_document(CANONICAL_GRAPH_PATH)

        validate_canonical_uuid_graph(graph)

        self.assertEqual(
            graph["contracts"]["sourceType"],
            ["manual"],
        )
        self.assertEqual(
            graph["contracts"]["reportModes"],
            ["shared_family_report", "combined_viewer_overview"],
        )
        self.assertEqual(
            graph["contracts"]["transferScopes"],
            ["personal_same_owner", "household_same_household"],
        )
        self.assertIn("/api/v1/transfers", graph["contracts"]["forbiddenRouteFamilies"])

    def test_w3_ttr_contract_bundle_covers_actors_goldens_and_no_runtime_seed(self) -> None:
        bundle = load_ttr_fixture_contracts(FIXTURE_ROOT)
        data = bundle.as_dict()

        self.assertEqual(
            set(bundle.contractSummary["canonicalActors"]),
            {"owner_a", "member_b", "other_c", "invited_ab", "former_ab"},
        )
        self.assertGreaterEqual(bundle.contractSummary["counts"]["accounts"], 12)
        self.assertGreaterEqual(bundle.contractSummary["counts"]["plannedTransactions"], 9)
        self.assertGreaterEqual(bundle.contractSummary["counts"]["plannedTransfers"], 12)
        self.assertGreaterEqual(bundle.contractSummary["counts"]["goldenCases"], 16)
        self.assertEqual(
            bundle.contractSummary["runtimeMountState"],
            "not_mounted_until_runtime_worker",
        )
        self.assertEqual(
            set(bundle.goldenExpectations),
            {"visibility", "reports", "transfer_denials"},
        )
        assert_safe_evidence_keys(data)

    def test_w3_ttr_contract_validation_rejects_enum_expansion(self) -> None:
        graph = load_json_document(CANONICAL_GRAPH_PATH)
        graph["contracts"]["sourceType"] = ["manual", "bank_api"]

        with self.assertRaises(FixtureContractError):
            validate_canonical_uuid_graph(graph)


if __name__ == "__main__":
    unittest.main()
