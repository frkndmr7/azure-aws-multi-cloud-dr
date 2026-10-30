"""Fail-closed outbox sequencing; deployment adapters are not wired to a live feed."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.models import URLRecord


@dataclass(frozen=True)
class Checkpoint:
    token: str | None
    etag: str | None


@dataclass(frozen=True)
class Page:
    records: list[dict[str, Any]]
    continuation: str


class NoChanges(Exception):
    """No safely checkpointable page was returned."""


class Lease(Protocol):
    def renew(self) -> None: ...


class Outbox(Protocol):
    def put_if_absent(self, event_id: str, message: str) -> None: ...
    def mark_sent(self, item: dict[str, Any]) -> None: ...
    def mark_failed(self, item: dict[str, Any], retry_at: str) -> None: ...


class Checkpoints(Protocol):
    def load(self, range_id: str) -> Checkpoint: ...
    def save(self, range_id: str, token: str, previous: Checkpoint) -> None: ...


class Feed(Protocol):
    def read_page(self, range_id: str, token: str | None) -> Page: ...


class Sender(Protocol):
    def send(self, message: str) -> None: ...


def make_event(document: dict[str, Any]) -> tuple[str, str]:
    record = URLRecord.model_validate(document)
    if record.origin_cloud != "azure" or record.writer_epoch < 0 or record.version < 1:
        raise ValueError("Invalid source or version")
    message = json.dumps({"schema_version": 1, "record": record.model_dump(mode="json")},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(message.encode("utf-8")).hexdigest(), message


def ingest_one_page(feed: Feed, outbox: Outbox, checkpoints: Checkpoints, range_id: str, lease: Lease) -> int:
    lease.renew()
    previous = checkpoints.load(range_id)
    try:
        page = feed.read_page(range_id, previous.token)
    except NoChanges:
        return 0
    if not page.continuation:
        raise ValueError("Feed continuation is required before checkpointing")
    for document in page.records:
        lease.renew()
        event_id, message = make_event(document)
        outbox.put_if_absent(event_id, message)
    lease.renew()
    checkpoints.save(range_id, page.continuation, previous)
    return len(page.records)


class DisabledSender:
    def send(self, message: str) -> None:
        raise RuntimeError("SQS dispatcher disabled: federation has not been verified")


def dispatch_one(outbox: Outbox, item: dict[str, Any], sender: Sender | None = None,
                 now: datetime | None = None) -> bool:
    # The default path fails closed and never constructs an AWS client.
    sender = sender if sender is not None else DisabledSender()
    try:
        sender.send(item["message"])
    except Exception:
        attempts = int(item.get("attempts", 0)) + 1
        delay = min(3600, 2 ** min(attempts, 12))
        retry_at = ((now or datetime.now(timezone.utc)) + timedelta(seconds=delay)).isoformat()
        outbox.mark_failed(item, retry_at)
        return False
    outbox.mark_sent(item)
    return True
