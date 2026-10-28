from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoints() -> None:
    client = TestClient(create_app(settings=Settings(cloud="aws", writer_mode="standby", writer_epoch=4)))
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    assert client.get("/health/dr").json() == {"cloud_role": "aws", "writer_mode": "standby", "writer_epoch": 4}
