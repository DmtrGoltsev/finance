from fastapi.testclient import TestClient

from app.config import Settings
from app.dev_seed import (
    DEV_DEMO_EMAIL,
    DEV_DEMO_HOUSEHOLD_ID,
    DEV_DEMO_PASSWORD,
    DEV_DEMO_SHARED_ACCOUNT_ID,
    DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID,
    DEV_DEMO_TRANSFER_TRANSACTION_ID,
    create_seeded_dev_app,
)
from app.main import create_app


def test_local_dev_cors_allows_vite_pwa_origin() -> None:
    app = create_app(Settings(environment="local"))

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://127.0.0.1:5174",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()


def test_local_dev_cors_allows_default_vite_pwa_origin_with_credentials() -> None:
    app = create_app(Settings(environment="local"))

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()


def test_production_like_cors_does_not_enable_dev_origins_by_default() -> None:
    app = create_app(Settings(environment="production"))

    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5174",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers


def test_seeded_dev_app_supports_login_and_minimal_data_smoke() -> None:
    app = create_seeded_dev_app(Settings(environment="local"))

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/sessions",
            json={
                "email": DEV_DEMO_EMAIL,
                "password": DEV_DEMO_PASSWORD,
                "transport": "android_bearer",
            },
        )
        token = login.json()["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        accounts = client.get("/api/v1/accounts", headers=headers)
        categories = client.get("/api/v1/categories", headers=headers)
        transactions = client.get("/api/v1/transactions", headers=headers)
        transfers = client.get(
            "/api/v1/transactions",
            params={"transactionType": "transfer"},
            headers=headers,
        )
        summary = client.get(
            "/api/v1/reports/summary",
            params={
                "reportMode": "combined_viewer_overview",
                "householdId": DEV_DEMO_HOUSEHOLD_ID,
                "currency": "USD",
            },
            headers=headers,
        )

    assert login.status_code == 201
    assert accounts.status_code == 200
    assert categories.status_code == 200
    assert transactions.status_code == 200
    assert transfers.status_code == 200
    assert summary.status_code == 200
    assert len(accounts.json()["items"]) == 3
    assert len(categories.json()["items"]) == 3
    assert len(transactions.json()["items"]) == 3
    transfer_items = transfers.json()["items"]
    assert len(transfer_items) == 1
    assert transfer_items[0]["id"] == DEV_DEMO_TRANSFER_TRANSACTION_ID
    assert transfer_items[0]["transactionType"] == "transfer"
    assert transfer_items[0]["accountId"] == DEV_DEMO_SHARED_ACCOUNT_ID
    assert transfer_items[0]["counterpartyAccountId"] == DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID
    assert transfer_items[0]["categoryId"] is None
    assert transfer_items[0]["transferScope"] == "household_same_household"
    assert transfer_items[0]["transferStatus"] == "posted"
    assert summary.json()["data"]["totalsByCurrency"]
