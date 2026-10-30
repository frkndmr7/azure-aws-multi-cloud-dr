"""Finite Azure Blob lease guard; the caller must use a pre-existing lock blob."""

from typing import Any


class BlobLeaseGuard:
    def __init__(self, lease_client: Any) -> None:
        self._lease = lease_client
        self._held = False

    def __enter__(self) -> "BlobLeaseGuard":
        self._lease.acquire(lease_duration=60)
        self._held = True
        return self

    def renew(self) -> None:
        if not self._held:
            raise RuntimeError("Worker lease is not held")
        try:
            self._lease.renew()
        except Exception:
            self._held = False
            raise

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._held:
            self._held = False
            self._lease.release()
