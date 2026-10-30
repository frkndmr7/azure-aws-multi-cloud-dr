from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from boto3.dynamodb.types import TypeSerializer
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import URLRecord
from app.repositories.dynamodb import DynamoDBRepository


@pytest.fixture
def record() -> URLRecord:
    now = datetime.now(timezone.utc)
    return URLRecord(id="abc", original_url="https://example.com/", created_at=now,
                     updated_at=now, origin_cloud="azure", writer_epoch=1)


@pytest.fixture
def table():
    resource = boto3.resource("dynamodb", region_name="eu-west-1",
                              aws_access_key_id="test", aws_secret_access_key="test")
    with Stubber(resource.meta.client) as stubber:
        yield resource.Table("urls-test"), stubber
    resource.meta.client.close()


def test_create_conditional(table, record: URLRecord) -> None:
    dynamo_table, stubber = table
    stubber.add_response("put_item", {}, {"TableName": "urls-test", "Item": record.model_dump(mode="json"),
                                         "ConditionExpression": "attribute_not_exists(#id)",
                                         "ExpressionAttributeNames": {"#id": "id"}})
    assert DynamoDBRepository(dynamo_table).create_if_absent(record)
    stubber.assert_no_pending_responses()


def test_collision_returns_false(table, record: URLRecord) -> None:
    dynamo_table, stubber = table
    stubber.add_client_error("put_item", service_error_code="ConditionalCheckFailedException", http_status_code=400)
    assert not DynamoDBRepository(dynamo_table).create_if_absent(record)


def test_point_read_and_missing(table, record: URLRecord) -> None:
    dynamo_table, stubber = table
    doc = record.model_dump(mode="json")
    doc["writer_epoch"] = Decimal(doc["writer_epoch"])
    doc["version"] = Decimal(doc["version"])
    encoded = {key: TypeSerializer().serialize(value) for key, value in doc.items()}
    stubber.add_response("get_item", {"Item": encoded}, {"TableName": "urls-test", "Key": {"id": "abc"}, "ConsistentRead": True})
    stubber.add_response("get_item", {}, {"TableName": "urls-test", "Key": {"id": "missing"}, "ConsistentRead": True})
    repo = DynamoDBRepository(dynamo_table)
    assert repo.get_by_id("abc") == record
    assert repo.get_by_id("missing") is None


def test_other_aws_error_is_sanitized(record: URLRecord) -> None:
    table = MagicMock()
    table.get_item.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "sensitive"}}, "GetItem")
    repo = DynamoDBRepository(table)
    with pytest.raises(ClientError):
        repo.get_by_id(record.id)
    client = TestClient(create_app(repository=repo), raise_server_exceptions=False)
    response = client.get("/abc")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_configuration_requires_region_and_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOSITORY_BACKEND", "dynamodb")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE", raising=False)
    with pytest.raises(ValueError, match="AWS_REGION.*DYNAMODB_TABLE"):
        Settings.from_env()
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("DYNAMODB_TABLE", "urls-test")
    settings = Settings.from_env()
    assert settings.aws_region == "eu-west-1" and settings.dynamodb_table == "urls-test"


def test_backend_lifecycle_and_standby(monkeypatch: pytest.MonkeyPatch) -> None:
    resource = MagicMock()
    factory = MagicMock(return_value=resource)
    monkeypatch.setattr(boto3, "resource", factory)
    settings = Settings(cloud="aws", writer_mode="standby", repository_backend="dynamodb",
                        aws_region="eu-west-1", dynamodb_table="urls-test")
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/urls", json={"original_url": "https://example.com"}).status_code == 403
        resource.Table.return_value.put_item.assert_not_called()
    factory.assert_called_once_with("dynamodb", region_name="eu-west-1")
    resource.Table.assert_called_once_with("urls-test")
    resource.meta.client.close.assert_called_once()
