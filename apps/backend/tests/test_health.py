def test_app_imports() -> None:
    from app.main import app

    assert app is not None


def test_health_endpoint(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
