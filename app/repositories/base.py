from typing import Protocol

from app.models import URLRecord


class URLRepository(Protocol):
    def create_if_absent(self, record: URLRecord) -> bool:
        """Create a record, returning False if its ID already exists."""
        ...

    def get_by_id(self, code: str) -> URLRecord | None:
        ...
