import logging
import secrets
import string
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings
from app.models import CreateURL, URLRecord
from app.repositories.base import URLRepository
from app.repositories.memory import InMemoryRepository

logger = logging.getLogger(__name__)
CODE_ALPHABET = string.ascii_letters + string.digits
MAX_CODE_ATTEMPTS = 5


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def create_app(settings: Settings | None = None, repository: URLRepository | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if repository is not None or settings.repository_backend == "memory":
            yield
            return
        if settings.repository_backend == "dynamodb":
            import boto3
            from starlette.concurrency import run_in_threadpool
            from app.repositories.dynamodb import DynamoDBRepository

            dynamodb = await run_in_threadpool(boto3.resource, "dynamodb", region_name=settings.aws_region)
            try:
                app.state.repository = DynamoDBRepository(dynamodb.Table(settings.dynamodb_table))
                yield
            finally:
                await run_in_threadpool(dynamodb.meta.client.close)
            return
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
        from starlette.concurrency import run_in_threadpool

        credential = DefaultAzureCredential()
        client = None
        try:
            client = await run_in_threadpool(CosmosClient, settings.cosmos_endpoint, credential)
            container = client.get_database_client(settings.cosmos_database).get_container_client(settings.cosmos_container)
            from app.repositories.cosmos import CosmosRepository
            app.state.repository = CosmosRepository(container)
            yield
        finally:
            try:
                if client is not None:
                    await run_in_threadpool(client.close)
            finally:
                await run_in_threadpool(credential.close)

    app = FastAPI(title="URL Shortener", lifespan=lifespan)
    if repository is not None:
        app.state.repository = repository
    elif settings.repository_backend == "memory":
        app.state.repository = InMemoryRepository()

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected application error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.post("/api/urls", response_model=URLRecord, status_code=status.HTTP_201_CREATED)
    def create_url(payload: CreateURL) -> URLRecord:
        if settings.writer_mode == "standby":
            raise HTTPException(status_code=403, detail="Writes are disabled in standby mode")
        if settings.writer_mode == "frozen":
            raise HTTPException(status_code=503, detail="Writes are temporarily frozen", headers={"Retry-After": "60"})
        for _ in range(MAX_CODE_ATTEMPTS):
            now = datetime.now(timezone.utc)
            record = URLRecord(id=generate_code(), original_url=str(payload.original_url), created_at=now,
                               updated_at=now, origin_cloud=settings.cloud, writer_epoch=settings.writer_epoch)
            if app.state.repository.create_if_absent(record):
                return record
        raise HTTPException(status_code=503, detail="Unable to allocate a short code; please retry")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/health/dr")
    def dr() -> dict[str, str | int]:
        return {"cloud_role": settings.cloud, "writer_mode": settings.writer_mode, "writer_epoch": settings.writer_epoch}

    @app.get("/api/urls/{code}", response_model=URLRecord)
    def get_url(code: str) -> URLRecord:
        record = app.state.repository.get_by_id(code)
        if record is None or record.deleted:
            raise HTTPException(status_code=404, detail="Short code not found")
        return record

    @app.get("/{code}")
    def redirect(code: str) -> RedirectResponse:
        record = get_url(code)
        return RedirectResponse(url=record.original_url, status_code=307)

    return app


app = create_app()
