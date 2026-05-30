from app.core.config import settings


def test_health_check(client) -> None:
    response = client.get(f"{settings.API_V1_PREFIX}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
