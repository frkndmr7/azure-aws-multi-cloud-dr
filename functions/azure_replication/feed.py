"""Conservative one-physical-range pull adapter; split/topology changes stop processing."""

import hashlib
import json
from typing import Any

from functions.azure_replication.core import NoChanges, Page


def range_identity(feed_range: dict[str, Any]) -> str:
    encoded = json.dumps(feed_range, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class SingleRangeFeed:
    def __init__(self, container: Any, page_size: int = 100) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.container = container
        self.page_size = page_size

    def current_range_id(self) -> str:
        ranges = list(self.container.read_feed_ranges(force_refresh=True))
        if len(ranges) != 1:
            raise RuntimeError("Unsupported feed topology; operator intervention required")
        return range_identity(ranges[0])

    def read_page(self, range_id: str, token: str | None) -> Page:
        ranges = list(self.container.read_feed_ranges(force_refresh=True))
        if len(ranges) != 1 or range_identity(ranges[0]) != range_id:
            raise RuntimeError("Feed range changed; checkpoint must not advance")
        if token is not None and (not token or token.strip("'\"").isdigit()):
            raise RuntimeError("Legacy or invalid continuation token is unsupported")
        kwargs: dict[str, Any] = {"feed_range": ranges[0], "max_item_count": self.page_size,
                                  "mode": "LatestVersion"}
        if token is None:
            kwargs["start_time"] = "Beginning"
        else:
            kwargs["continuation"] = token
        pages = self.container.query_items_change_feed(**kwargs).by_page()
        try:
            records = list(next(pages))
        except StopIteration:
            # SDK may stop on an empty/304 response. Keep the old checkpoint.
            raise NoChanges from None
        continuation = pages.continuation_token
        if not continuation:
            raise RuntimeError("SDK returned a page without a continuation token")
        # A topology change during a request is not automatically accepted.
        if self.current_range_id() != range_id:
            raise RuntimeError("Feed range changed during read; checkpoint must not advance")
        return Page(records, continuation)
