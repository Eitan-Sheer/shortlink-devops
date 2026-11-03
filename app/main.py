import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app import db, repository
from app.config import Settings, get_settings

logger = logging.getLogger("shortlink")

REQUEST_LATENCY = Histogram(
    "shortlink_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status"],
)
REDIRECTS_TOTAL = Counter("shortlink_redirects_total", "Number of successful redirects")
LINKS_CREATED_TOTAL = Counter("shortlink_links_created_total", "Number of links created")


class CreateLinkRequest(BaseModel):
    url: HttpUrl


class LinkResponse(BaseModel):
    code: str
    target_url: str
    short_url: str
    clicks: int


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    engine = db.build_engine(settings.database_url)
    session_factory = db.make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.init_db(engine)
        logger.info("startup complete version=%s", settings.app_version)
        yield
        engine.dispose()
        logger.info("shutdown complete")

    app = FastAPI(title="shortlink", version=settings.app_version, lifespan=lifespan)

    def get_session() -> Iterator[Session]:
        yield from db.session_scope(session_factory)

    SessionDep = Annotated[Session, Depends(get_session)]

    @app.middleware("http")
    async def observe(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        REQUEST_LATENCY.labels(request.method, path, response.status_code).observe(
            time.perf_counter() - started
        )
        return response

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz() -> dict[str, str]:
        if not db.ping(engine):
            raise HTTPException(status_code=503, detail="database unavailable")
        return {"status": "ready"}

    @app.get("/version", tags=["ops"])
    def version() -> dict[str, str]:
        return {"version": settings.app_version}

    @app.get("/metrics", tags=["ops"])
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/links", response_model=LinkResponse, status_code=201, tags=["links"])
    def create_link(payload: CreateLinkRequest, session: SessionDep) -> LinkResponse:
        link = repository.create_link(session, str(payload.url))
        LINKS_CREATED_TOTAL.inc()
        return LinkResponse(
            code=link.code,
            target_url=link.target_url,
            short_url=f"{settings.base_url}/{link.code}",
            clicks=link.clicks,
        )

    @app.get("/links/{code}", response_model=LinkResponse, tags=["links"])
    def get_link(code: str, session: SessionDep) -> LinkResponse:
        link = repository.get_link(session, code)
        if link is None:
            raise HTTPException(status_code=404, detail="link not found")
        return LinkResponse(
            code=link.code,
            target_url=link.target_url,
            short_url=f"{settings.base_url}/{link.code}",
            clicks=link.clicks,
        )

    @app.get("/{code}", tags=["links"])
    def redirect(code: str, session: SessionDep) -> RedirectResponse:
        link = repository.get_link(session, code)
        if link is None:
            raise HTTPException(status_code=404, detail="link not found")
        repository.register_click(session, code)
        REDIRECTS_TOTAL.inc()
        return RedirectResponse(url=link.target_url, status_code=302)

    return app


app = create_app()
