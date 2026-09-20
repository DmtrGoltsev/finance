"""Сравнение всего публичного инвестиционного контракта, а не списка избранных полей."""

import copy
import json
from pathlib import Path

import pytest
import yaml

CONTRACT = Path(__file__).resolve().parents[4] / "api/openapi/openapi.yaml"
ANNOTATIONS = {"title", "description", "examples", "example", "$comment"}


def normalized(value, document):
    if isinstance(value, list):
        return [normalized(item, document) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        target = document
        for part in value["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return normalized({**target, **{k: v for k, v in value.items() if k != "$ref"}}, document)
    result = {}
    for key, item in value.items():
        if key in ANNOTATIONS:
            continue
        result[key] = (
            {name: normalized(schema, document) for name, schema in item.items()}
            if key == "properties" else normalized(item, document)
        )
        if (
            key in {"required", "enum", "anyOf", "oneOf", "allOf", "type"}
            and isinstance(item, list)
        ):
            result[key] = sorted(result[key], key=lambda item: json.dumps(item, sort_keys=True))
    return result


def assert_contract(static, runtime):
    runtime_paths = {
        path.removeprefix("/api/v1"): operations
        for path, operations in runtime["paths"].items()
        if path.startswith("/api/v1/investments/")
    }
    static_paths = {
        path: operations for path, operations in static["paths"].items()
        if path.startswith("/investments/")
    }
    assert set(static_paths) == set(runtime_paths)
    visited = set()

    def collect_refs(value, document):
        if isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].rsplit("/", 1)[-1]
                if name not in visited:
                    visited.add(name)
                    collect_refs(document["components"]["schemas"][name], document)
            for item in value.values():
                collect_refs(item, document)
        elif isinstance(value, list):
            for item in value:
                collect_refs(item, document)

    for path, operations in runtime_paths.items():
        assert set(static_paths[path]) == set(operations), path
        for method, operation in operations.items():
            approved = static_paths[path][method]
            assert approved["operationId"] == operation["operationId"]
            def parameters(op, doc):
                return {
                    (parameter["in"], parameter["name"]): normalized(parameter, doc)
                    for parameter in op.get("parameters", [])
                }
            assert parameters(approved, static) == parameters(operation, runtime), (
                path, method, "parameters"
            )
            for part in ("requestBody",):
                assert normalized(approved.get(part), static) == normalized(
                    operation.get(part), runtime
                ), (path, method, part)
                collect_refs(operation.get(part), runtime)
            successes = {code for code in approved["responses"] if code.startswith("2")}
            assert successes == {code for code in operation["responses"] if code.startswith("2")}
            for code in successes:
                assert normalized(approved["responses"][code], static) == normalized(
                    operation["responses"][code], runtime
                ), (path, method, code)
                collect_refs(operation["responses"][code], runtime)
            def hmac_headers(op, doc):
                return {
                    parameter["name"].lower(): normalized(parameter, doc)
                    for parameter in op.get("parameters", [])
                    if parameter.get("in") == "header"
                    and parameter.get("name", "").lower().startswith("x-finance-")
                }
            assert hmac_headers(approved, static) == hmac_headers(operation, runtime), path
    return visited


def test_all_public_investment_schemas_match_canonical_contract(client):
    static = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    runtime = client.get("/openapi.json").json()
    visited = assert_contract(static, runtime)
    assert {
        "InvestmentPolicyPutRequest", "PortfolioImportConfirmRequest", "RecommendationJobDto",
        "RecommendationCallbackRequest", "PortfolioPositionInput", "RecommendationReportDto",
    } <= visited
    # Every public model from this domain must be reachable through an operation comparison.
    from app.investments import schemas
    from app.investments.schemas import ApiModel
    public_models = {
        name for name, value in vars(schemas).items()
        if isinstance(value, type) and issubclass(value, ApiModel) and value is not ApiModel
    }
    visited_model_names = {name.rsplit("__", 1)[-1] for name in visited}
    assert public_models <= visited_model_names


@pytest.mark.parametrize("change", ["required", "nullable", "type", "header", "body"])
def test_comparator_detects_contract_drift(client, change):
    static = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    runtime = copy.deepcopy(client.get("/openapi.json").json())
    schemas = runtime["components"]["schemas"]
    callback = runtime["paths"][
        "/api/v1/investments/internal/recommendation-jobs/{jobId}/callback"
    ]["post"]
    if change == "required":
        schemas["InvestmentPolicyPutRequest"]["required"] = ["conservativePercent"]
    elif change == "nullable":
        schemas["RecommendationJobDto"]["properties"]["completedAt"] = {"type": "string"}
    elif change == "type":
        schemas["PortfolioImportConfirmRequest"]["properties"]["positions"]["type"] = "string"
    elif change == "header":
        next(p for p in callback["parameters"] if p["in"] == "header")["required"] = False
    else:
        callback["requestBody"]["required"] = False
    with pytest.raises(AssertionError):
        assert_contract(static, runtime)
