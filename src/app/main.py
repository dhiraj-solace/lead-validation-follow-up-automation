from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.core.config import settings
from src.app.api.endpoints import api_endpoints
from src.app.db.database import init_db

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


@app.on_event("startup")
def startup():
    init_db()


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
