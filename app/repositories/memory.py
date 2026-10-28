from threading import Lock

from app.models import URLRecord


class InMemoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, URLRecord] = {}
        self._lock = Lock()

    def create_if_absent(self, record: URLRecord) -> bool:
        with self._lock:
            if record.id in self._records:
                return False
            self._records[record.id] = record.model_copy(deep=True)
            return True

    def get_by_id(self, code: str) -> URLRecord | None:
        with self._lock:
            record = self._records.get(code)
            return record.model_copy(deep=True) if record else None
