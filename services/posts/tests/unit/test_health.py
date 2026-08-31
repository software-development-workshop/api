from fastapi.testclient import TestClient

from posts import main


def test_health_reports_the_service_is_up() -> None:
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
