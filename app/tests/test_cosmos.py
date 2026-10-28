from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceExistsError, CosmosResourceNotFoundError
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import URLRecord
from app.repositories.cosmos import CosmosRepository
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def record() -> URLRecord:
    now = datetime.now(timezone.utc)
    return URLRecord(id="abc", original_url="https://example.com/", created_at=now,
                     updated_at=now, origin_cloud="azure", writer_epoch=1)


def test_create_document(record: URLRecord) -> None:
    container = MagicMock()
    assert CosmosRepository(container).create_if_absent(record)
    doc = container.create_item.call_args.kwargs["body"]
    assert set(doc) == {"id", "original_url", "created_at", "updated_at", "origin_cloud", "writer_epoch", "version", "deleted"}
    assert doc == record.model_dump(mode="json")
    assert datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0


def test_conflict(record: URLRecord) -> None:
    container = MagicMock()
    container.create_item.side_effect = CosmosResourceExistsError(message="conflict")
    assert not CosmosRepository(container).create_if_absent(record)
    container.create_item.assert_called_once()


def test_point_read(record: URLRecord) -> None:
    container = MagicMock()
    container.read_item.return_value = {**record.model_dump(mode="json"), "_etag": "metadata"}
    assert CosmosRepository(container).get_by_id("abc") == record
    container.read_item.assert_called_once_with(item="abc", partition_key="abc")


def test_not_found() -> None:
    container = MagicMock()
    container.read_item.side_effect = CosmosResourceNotFoundError(message="not found")
    assert CosmosRepository(container).get_by_id("missing") is None


def test_service_error_propagates_and_http_is_sanitized(record: URLRecord) -> None:
    container = MagicMock()
    container.create_item.side_effect = CosmosHttpResponseError(status_code=403, message="sensitive details")
    repo = CosmosRepository(container)
    with pytest.raises(CosmosHttpResponseError):
        repo.create_if_absent(record)
    client = TestClient(create_app(repository=repo), raise_server_exceptions=False)
    response = client.post("/api/urls", json={"original_url": "https://example.com"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    app = create_app(settings=Settings.from_env())
    assert isinstance(app.state.repository, InMemoryRepository)


def test_missing_cosmos_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOSITORY_BACKEND", "cosmos")
    for key in ("COSMOS_ENDPOINT", "COSMOS_DATABASE", "COSMOS_CONTAINER"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="COSMOS_ENDPOINT.*COSMOS_DATABASE.*COSMOS_CONTAINER"):
        Settings.from_env()


def test_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOSITORY_BACKEND", "other")
    with pytest.raises(ValueError, match="REPOSITORY_BACKEND"):
        Settings.from_env()


def test_cosmos_client_lifecycle(monkeypatch: pytest.MonkeyPatch, record: URLRecord) -> None:
    credential = MagicMock()
    client = MagicMock()
    container = client.get_database_client.return_value.get_container_client.return_value
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("azure.cosmos.CosmosClient", factory)
    settings = Settings(repository_backend="cosmos", cosmos_endpoint="https://example.invalid",
                        cosmos_database="db", cosmos_container="urls")
    with TestClient(create_app(settings=settings)) as test_client:
        assert test_client.post("/api/urls", json={"original_url": "https://example.com"}).status_code == 201
        assert test_client.post("/api/urls", json={"original_url": "https://example.com"}).status_code == 201
    factory.assert_called_once_with("https://example.invalid", credential)
    client.get_database_client.assert_called_once_with("db")
    client.get_database_client.return_value.get_container_client.assert_called_once_with("urls")
    assert container.create_item.call_count == 2
    client.close.assert_called_once()
    credential.close.assert_called_once()


def test_startup_failure_closes_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    credential = MagicMock()
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    factory = MagicMock(side_effect=RuntimeError("connection failed"))
    monkeypatch.setattr("azure.cosmos.CosmosClient", factory)
    settings = Settings(repository_backend="cosmos", cosmos_endpoint="https://example.invalid",
                        cosmos_database="db", cosmos_container="urls")
    with pytest.raises(RuntimeError, match="connection failed"):
        with TestClient(create_app(settings=settings)):
            pass
    credential.close.assert_called_once()
