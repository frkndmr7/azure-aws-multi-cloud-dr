import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from azure.cosmos.exceptions import CosmosResourceExistsError

from functions.azure_replication.core import Checkpoint, Page, dispatch_one, ingest_one_page, make_event
from functions.azure_replication.cosmos_store import CosmosCheckpoints, CosmosOutbox


def document():
    return {"id": "abc", "original_url": "https://example.com/", "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "origin_cloud": "azure", "writer_epoch": 1,
            "version": 1, "deleted": False, "_etag": "ignored"}


def test_checkpoint_only_after_all_writes():
    feed = MagicMock(); feed.read_page.return_value = Page([document(), {**document(), "id": "def"}], "next")
    outbox = MagicMock(); outbox.put_if_absent.side_effect = [None, RuntimeError("storage failed")]
    checkpoints = MagicMock(); checkpoints.load.return_value = Checkpoint("old", "etag")
    with pytest.raises(RuntimeError):
        ingest_one_page(feed, outbox, checkpoints, "range", MagicMock())
    checkpoints.save.assert_not_called()


def test_crash_between_outbox_and_checkpoint_replays_deterministically():
    feed = MagicMock(); feed.read_page.return_value = Page([document()], "next")
    outbox = MagicMock(); checkpoints = MagicMock(); checkpoints.load.return_value = Checkpoint("old", "etag")
    checkpoints.save.side_effect = [RuntimeError("crash"), None]
    with pytest.raises(RuntimeError):
        ingest_one_page(feed, outbox, checkpoints, "range", MagicMock())
    assert ingest_one_page(feed, outbox, checkpoints, "range", MagicMock()) == 1
    assert outbox.put_if_absent.call_args_list[0] == outbox.put_if_absent.call_args_list[1]
    event_id, message = make_event(document())
    assert len(event_id) == 64 and json.loads(message)["record"]["id"] == "abc"


def test_missing_continuation_never_writes_or_checkpoints():
    feed = MagicMock(); feed.read_page.return_value = Page([document()], "")
    outbox = MagicMock(); checkpoints = MagicMock()
    with pytest.raises(ValueError): ingest_one_page(feed, outbox, checkpoints, "range", MagicMock())
    outbox.put_if_absent.assert_not_called(); checkpoints.save.assert_not_called()


def test_outbox_conflict_never_overwrites_sent_record():
    container = MagicMock(); container.create_item.side_effect = CosmosResourceExistsError(message="exists")
    container.read_item.return_value = {"id": "event", "message": "same", "state": "sent"}
    store = CosmosOutbox(container); store.put_if_absent("event", "same")
    container.replace_item.assert_not_called()
    with pytest.raises(ValueError): store.put_if_absent("event", "different")


def test_checkpoint_compare_and_swap():
    container = MagicMock(); store = CosmosCheckpoints(container)
    store.save("range", "next", Checkpoint("old", "etag"))
    assert container.replace_item.call_args.kwargs["etag"] == "etag"
    container.replace_item.side_effect = RuntimeError("etag conflict")
    with pytest.raises(RuntimeError): store.save("range", "next", Checkpoint("old", "etag"))


def test_dispatch_fail_closed_and_retry_without_marking_sent():
    outbox = MagicMock(); item = {"message": "{}", "attempts": 2}
    assert not dispatch_one(outbox, item, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    outbox.mark_failed.assert_called_once(); outbox.mark_sent.assert_not_called()
    assert outbox.mark_failed.call_args.args[1] == "2026-01-01T00:00:08+00:00"


def test_send_success_then_mark_failure_can_replay_duplicate():
    sender = MagicMock(); outbox = MagicMock(); item = {"message": "{}", "attempts": 0}
    outbox.mark_sent.side_effect = [RuntimeError("crash"), None]
    with pytest.raises(RuntimeError): dispatch_one(outbox, item, sender)
    assert dispatch_one(outbox, item, sender)
    assert sender.send.call_count == 2


def test_sender_error_keeps_backlog():
    sender = MagicMock(); sender.send.side_effect = RuntimeError("temporary")
    outbox = MagicMock()
    assert not dispatch_one(outbox, {"message": "{}", "attempts": 0}, sender)
    outbox.mark_sent.assert_not_called(); outbox.mark_failed.assert_called_once()


def test_timer_entrypoints_fail_closed(monkeypatch):
    pytest.importorskip("azure.functions")
    from functions.azure_replication.function_app import app
    functions = {f.get_function_name(): f.get_user_function() for f in app.get_functions()}
    for name, setting in [("producer", "PRODUCER_ENABLED"), ("dispatcher", "DISPATCHER_ENABLED")]:
        monkeypatch.setenv(setting, "false")
        functions[name](None)
        monkeypatch.setenv(setting, "true")
        with pytest.raises(RuntimeError, match="disabled"):
            functions[name](None)


def test_single_range_feed_captures_only_the_returned_page_token():
    from functions.azure_replication.feed import SingleRangeFeed
    container = MagicMock(); container.read_feed_ranges.return_value = [{"min": "A", "max": "Z"}]
    pages = MagicMock(); pages.__next__.return_value = iter([document()]); pages.continuation_token = "token-v2"
    container.query_items_change_feed.return_value.by_page.return_value = pages
    adapter = SingleRangeFeed(container)
    result = adapter.read_page(adapter.current_range_id(), None)
    assert result.records == [document()] and result.continuation == "token-v2"
    assert container.query_items_change_feed.call_args.kwargs["start_time"] == "Beginning"


def test_feed_empty_and_topology_change_fail_closed():
    from functions.azure_replication.core import NoChanges
    from functions.azure_replication.feed import SingleRangeFeed
    container = MagicMock(); container.read_feed_ranges.return_value = [{"min": "A", "max": "Z"}]
    pages = MagicMock(); pages.__next__.side_effect = StopIteration
    container.query_items_change_feed.return_value.by_page.return_value = pages
    adapter = SingleRangeFeed(container); range_id = adapter.current_range_id()
    with pytest.raises(NoChanges): adapter.read_page(range_id, None)
    container.read_feed_ranges.return_value = [{"min": "A", "max": "M"}, {"min": "M", "max": "Z"}]
    with pytest.raises(RuntimeError, match="Feed range changed"): adapter.read_page(range_id, "token-v2")


def test_feed_missing_token_and_timeout_do_not_checkpoint():
    from functions.azure_replication.feed import SingleRangeFeed
    container = MagicMock(); container.read_feed_ranges.return_value = [{"min": "A", "max": "Z"}]
    pages = MagicMock(); pages.__next__.return_value = iter([document()]); pages.continuation_token = None
    container.query_items_change_feed.return_value.by_page.return_value = pages
    feed = SingleRangeFeed(container); checkpoint = MagicMock(); checkpoint.load.return_value = Checkpoint(None, None)
    with pytest.raises(RuntimeError, match="without a continuation"):
        ingest_one_page(feed, MagicMock(), checkpoint, feed.current_range_id(), MagicMock())
    checkpoint.save.assert_not_called()
    pages.__next__.side_effect = TimeoutError("timeout")
    with pytest.raises(TimeoutError):
        ingest_one_page(feed, MagicMock(), checkpoint, feed.current_range_id(), MagicMock())
    checkpoint.save.assert_not_called()


def test_lost_lease_prevents_checkpoint():
    feed = MagicMock(); feed.read_page.return_value = Page([document()], "next")
    outbox = MagicMock(); checkpoint = MagicMock(); checkpoint.load.return_value = Checkpoint("old", "etag")
    lease = MagicMock(); lease.renew.side_effect = [None, None, RuntimeError("lease lost")]
    with pytest.raises(RuntimeError, match="lease lost"):
        ingest_one_page(feed, outbox, checkpoint, "range", lease)
    assert outbox.put_if_absent.call_count == 1
    checkpoint.save.assert_not_called()


def test_blob_lease_guard_rejects_unheld_and_lost_lease():
    from functions.azure_replication.lease import BlobLeaseGuard
    sdk = MagicMock(); guard = BlobLeaseGuard(sdk)
    with pytest.raises(RuntimeError, match="not held"): guard.renew()
    with guard:
        guard.renew()
    sdk.acquire.assert_called_once_with(lease_duration=60)
    sdk.release.assert_called_once()
    guard = BlobLeaseGuard(sdk); sdk.renew.side_effect = RuntimeError("lease lost")
    with pytest.raises(RuntimeError, match="lease lost"):
        with guard: guard.renew()
    assert sdk.release.call_count == 1
