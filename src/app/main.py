import logging
import sys
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.app.core.config import settings
from src.app.api.endpoints import api_endpoints
from src.app.db.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger("lead_automation")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_endpoints.router, prefix=f"{settings.API_V1_STR}/leads", tags=["leads"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex[:12]
    started_at = time.perf_counter()
    path = request.url.path
    logger.info("request.start id=%s method=%s path=%s", request_id, request.method, path)

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "request.error id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            path,
            duration_ms,
        )
        raise

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.end id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or uuid4().hex[:12]
    logger.error(
        "unhandled_exception id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"x-request-id": request_id},
    )


@app.on_event("startup")
def startup():
    logger.info(
        "app.startup database=%s demo_mode=%s data_dir=%s upload_dir=%s output_dir=%s",
        database_backend(),
        settings.DEMO_MODE,
        settings.DATA_DIR,
        settings.UPLOAD_DIR,
        settings.OUTPUT_DIR,
    )
    init_db()
    logger.info("app.startup.complete database=%s", database_backend())


@app.get("/")
def root():
    return {"message": "Welcome to Lead Validation API", "database": database_backend()}


@app.get("/api")
def api_health():
    return {"status": "ok", "message": "Lead Validation API is running", "database": database_backend()}


@app.get("/health")
def health():
    return {"status": "ok", "database": database_backend()}


def database_backend() -> str:
    return "mongodb" if settings.MONGODB_URI else "sqlite"
