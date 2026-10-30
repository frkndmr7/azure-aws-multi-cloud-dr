"""Cosmos-backed outbox and compare-and-swap checkpoints, not a worker lock."""

from typing import Any
from datetime import datetime, timezone
from itertools import islice

from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError

from functions.azure_replication.core import Checkpoint


class CosmosOutbox:
    def __init__(self, container: Any) -> None:
        self.container = container

    def put_if_absent(self, event_id: str, message: str) -> None:
        item = {"id": "evt-" + event_id, "message": message, "state": "pending", "attempts": 0,
                "created_at": datetime.now(timezone.utc).isoformat()}
        try:
            self.container.create_item(body=item)
        except CosmosResourceExistsError:
            existing = self.container.read_item(item=item["id"], partition_key=item["id"])
            if existing.get("message") != message:
                raise ValueError("Outbox event identity conflict")

    def mark_sent(self, item: dict[str, Any]) -> None:
        updated = {key: value for key, value in item.items() if not key.startswith("_")}
        updated["state"] = "sent"
        self.container.replace_item(item=item["id"], body=updated, etag=item["_etag"],
                                    match_condition=MatchConditions.IfNotModified)

    def mark_failed(self, item: dict[str, Any], retry_at: str) -> None:
        updated = {key: value for key, value in item.items() if not key.startswith("_")}
        updated.update(attempts=int(item.get("attempts", 0)) + 1, retry_at=retry_at)
        self.container.replace_item(item=item["id"], body=updated, etag=item["_etag"],
                                    match_condition=MatchConditions.IfNotModified)

    def pending(self, now: str, limit: int) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query = ("SELECT * FROM c WHERE c.state = @state AND "
                 "(NOT IS_DEFINED(c.retry_at) OR c.retry_at <= @now)")
        rows = self.container.query_items(query=query, parameters=[{"name": "@state", "value": "pending"},
                                           {"name": "@now", "value": now}],
                                          enable_cross_partition_query=True, max_item_count=limit)
        return list(islice(rows, limit))


class CosmosCheckpoints:
    def __init__(self, container: Any) -> None:
        self.container = container

    def load(self, range_id: str) -> Checkpoint:
        checkpoint_id = "ckpt-" + range_id
        try:
            item = self.container.read_item(item=checkpoint_id, partition_key=checkpoint_id)
        except CosmosResourceNotFoundError:
            return Checkpoint(None, None)
        return Checkpoint(item["continuation"], item["_etag"])

    def save(self, range_id: str, token: str, previous: Checkpoint) -> None:
        item = {"id": "ckpt-" + range_id, "continuation": token}
        if previous.etag is None:
            self.container.create_item(body=item)
        else:
            self.container.replace_item(item=item["id"], body=item, etag=previous.etag,
                                        match_condition=MatchConditions.IfNotModified)
