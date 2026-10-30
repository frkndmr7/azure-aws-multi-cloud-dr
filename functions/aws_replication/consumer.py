"""SQS replication consumer; failed messages remain eligible for retry/DLQ."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
_FIELDS = {"id", "original_url", "created_at", "updated_at", "origin_cloud", "writer_epoch", "version", "deleted"}


def validate_message(body: str) -> dict[str, Any]:
    envelope = json.loads(body)
    if not isinstance(envelope, dict) or envelope.get("schema_version") != 1:
        raise ValueError("Unsupported message schema")
    item = envelope.get("record")
    if not isinstance(item, dict) or set(item) != _FIELDS:
        raise ValueError("Invalid record fields")
    if not isinstance(item["id"], str) or not item["id"] or item["origin_cloud"] != "azure":
        raise ValueError("Invalid source identity")
    if not isinstance(item["original_url"], str) or not item["original_url"].startswith(("http://", "https://")):
        raise ValueError("Invalid URL")
    if type(item["writer_epoch"]) is not int or item["writer_epoch"] < 0 or type(item["version"]) is not int or item["version"] < 1 or type(item["deleted"]) is not bool:
        raise ValueError("Invalid version or deletion marker")
    for key in ("created_at", "updated_at"):
        if not isinstance(item[key], str) or datetime.fromisoformat(item[key].replace("Z", "+00:00")).utcoffset() is None:
            raise ValueError("Timestamp must include an offset")
    return item


def replicate(table: Any, item: dict[str, Any]) -> None:
    try:
        table.put_item(
            Item=item,
            ConditionExpression=("attribute_not_exists(#id) OR (#origin = :azure AND "
                                 "(#epoch < :epoch OR (#epoch = :epoch AND #version < :version)))"),
            ExpressionAttributeNames={"#id": "id", "#origin": "origin_cloud", "#epoch": "writer_epoch", "#version": "version"},
            ExpressionAttributeValues={":azure": "azure", ":epoch": item["writer_epoch"], ":version": item["version"]},
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        existing = table.get_item(Key={"id": item["id"]}, ConsistentRead=True).get("Item")
        if not existing or existing.get("origin_cloud") != "azure":
            raise ValueError("Source identity conflict") from exc
        current = (existing.get("writer_epoch"), existing.get("version"))
        incoming = (item["writer_epoch"], item["version"])
        if None in current:
            raise ValueError("Existing record has no ordering fields") from exc
        if current > incoming or (current == incoming and existing == item):
            return
        raise ValueError("Same version contains different data") from exc


def handle_batch(event: dict[str, Any], table: Any) -> dict[str, Any]:
    failures = []
    for record in event["Records"]:
        try:
            replicate(table, validate_message(record["body"]))
        except Exception:
            logger.warning("Replication message failed; retry or DLQ required")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    table = boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE"])
    return handle_batch(event, table)
