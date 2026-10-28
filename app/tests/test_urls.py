from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import URLRecord
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_create_and_redirect(client: TestClient) -> None:
    response = client.post("/api/urls", json={"original_url": "https://example.com/path"})
    assert response.status_code == 201
    record = response.json()
    assert record["original_url"] == "https://example.com/path"
    assert record["origin_cloud"] == "azure"
    assert record["writer_epoch"] == 1
    assert record["version"] == 1 and record["deleted"] is False
    assert datetime.fromisoformat(record["created_at"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert record["created_at"] == record["updated_at"]
    assert client.get(f"/api/urls/{record['id']}").json() == record
    redirect = client.get(f"/{record['id']}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == record["original_url"]


@pytest.mark.parametrize("url", ["", "ftp://example.com", "not-a-url", "https://example.com/" + "a" * 2048])
def test_invalid_url(client: TestClient, url: str) -> None:
    assert client.post("/api/urls", json={"original_url": url}).status_code == 422


def test_missing_code(client: TestClient) -> None:
    assert client.get("/missing").status_code == 404
    assert client.get("/api/urls/missing").status_code == 404


def test_collision_retries_without_overwriting(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryRepository()
    now = datetime.now(timezone.utc)
    existing = URLRecord(id="taken", original_url="https://old.example/", created_at=now, updated_at=now,
                         origin_cloud="azure", writer_epoch=1)
    assert repo.create_if_absent(existing)
    codes = iter(["taken", "newcode"])
    monkeypatch.setattr("app.main.generate_code", lambda: next(codes))
    response = TestClient(create_app(repository=repo)).post("/api/urls", json={"original_url": "https://new.example"})
    assert response.status_code == 201 and response.json()["id"] == "newcode"
    assert repo.get_by_id("taken") == existing


def test_collision_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.generate_code", lambda: "same")
    client = TestClient(create_app())
    assert client.post("/api/urls", json={"original_url": "https://example.com"}).status_code == 201
    assert client.post("/api/urls", json={"original_url": "https://example.com"}).status_code == 503


@pytest.mark.parametrize("mode,code", [("standby", 403), ("frozen", 503)])
def test_writer_modes(mode: str, code: int) -> None:
    client = TestClient(create_app(settings=Settings(writer_mode=mode)))
    response = client.post("/api/urls", json={"original_url": "https://example.com"})
    assert response.status_code == code
    assert mode in response.json()["detail"]
    if mode == "frozen":
        assert response.headers["retry-after"] == "60"


def test_unexpected_errors_are_sanitized() -> None:
    class BrokenRepository(InMemoryRepository):
        def get_by_id(self, code: str) -> URLRecord | None:
            raise RuntimeError("sensitive internal details")

    client = TestClient(create_app(repository=BrokenRepository()), raise_server_exceptions=False)
    response = client.get("/missing")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
