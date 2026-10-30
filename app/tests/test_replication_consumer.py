import json
from copy import deepcopy
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from functions.aws_replication.consumer import handle_batch, replicate, validate_message


def record(version=1, epoch=1, url="https://example.com/"):
    return {"id": "abc", "original_url": url, "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "origin_cloud": "azure",
            "writer_epoch": epoch, "version": version, "deleted": False}


def conditional_failure():
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "conflict"}}, "PutItem")


def test_duplicate_and_stale_are_safe():
    table = MagicMock()
    table.put_item.side_effect = conditional_failure()
    table.get_item.return_value = {"Item": record(version=2)}
    replicate(table, record(version=1))
    replicate(table, record(version=2))
    assert table.get_item.call_count == 2
    table.get_item.assert_called_with(Key={"id": "abc"}, ConsistentRead=True)


def test_partial_batch_and_replay():
    table = MagicMock()
    table.put_item.side_effect = [None, ClientError({"Error": {"Code": "ThrottlingException"}}, "PutItem")]
    event = {"Records": [{"messageId": "ok", "body": json.dumps({"schema_version": 1, "record": record()})},
                         {"messageId": "retry", "body": json.dumps({"schema_version": 1, "record": record(version=2)})}]}
    assert handle_batch(event, table) == {"batchItemFailures": [{"itemIdentifier": "retry"}]}
    table.put_item.side_effect = None
    assert handle_batch({"Records": [event["Records"][1]]}, table) == {"batchItemFailures": []}


def test_same_version_conflict_and_foreign_owner_retry():
    table = MagicMock()
    table.put_item.side_effect = conditional_failure()
    table.get_item.return_value = {"Item": record(url="https://other.example/")}
    msg = {"messageId": "conflict", "body": json.dumps({"schema_version": 1, "record": record()})}
    assert handle_batch({"Records": [msg]}, table)["batchItemFailures"] == [{"itemIdentifier": "conflict"}]
    other = deepcopy(record()); other["origin_cloud"] = "aws"
    table.get_item.return_value = {"Item": other}
    assert handle_batch({"Records": [msg]}, table)["batchItemFailures"] == [{"itemIdentifier": "conflict"}]


def test_invalid_message_goes_to_retry_without_write():
    table = MagicMock()
    event = {"Records": [{"messageId": "invalid", "body": "not-json"}]}
    assert handle_batch(event, table) == {"batchItemFailures": [{"itemIdentifier": "invalid"}]}
    table.put_item.assert_not_called()


def test_version_order_is_enforced_in_dynamodb():
    table = MagicMock()
    item = validate_message(json.dumps({"schema_version": 1, "record": record(version=3, epoch=2)}))
    replicate(table, item)
    args = table.put_item.call_args.kwargs
    assert "#epoch < :epoch" in args["ConditionExpression"]
    assert "#version < :version" in args["ConditionExpression"]
    assert args["ExpressionAttributeValues"][":epoch"] == 2
    assert args["ExpressionAttributeValues"][":version"] == 3
