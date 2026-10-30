import importlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import app.lambda_handler
import app.main
from app.config import Settings
from app.models import URLRecord


def event(method: str, path: str, body: dict | None = None) -> dict:
    return {
        "version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {"http": {"method": method, "path": path, "sourceIp": "127.0.0.1"}},
        "body": json.dumps(body) if body else None, "isBase64Encoded": False,
    }


def test_lambda_handler_redirect_and_standby(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    repo = MagicMock()
    repo.get_by_id.return_value = URLRecord(id="abc", original_url="https://example.com/",
                                           created_at=now, updated_at=now, origin_cloud="azure", writer_epoch=1)
    application = app.main.create_app(settings=Settings(cloud="aws", writer_mode="standby"), repository=repo)
    monkeypatch.setattr("app.main.app", application)
    handler = importlib.reload(app.lambda_handler).handler
    response = handler(event("GET", "/abc"), {})
    assert response["statusCode"] == 307
    assert response["headers"]["location"] == "https://example.com/"
    response = handler(event("POST", "/api/urls", {"original_url": "https://example.com/"}), {})
    assert response["statusCode"] == 403
    repo.create_if_absent.assert_not_called()
