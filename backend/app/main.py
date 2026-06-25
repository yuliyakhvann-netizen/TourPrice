from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import comparisons, mappings, operators, profiles, search
from app.core.logging import setup_logging
from app.database import engine
from app.models import *  # noqa: F401, F403 — registers all models with SQLAlchemy


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="TourPrice Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router, prefix="/api/v1")
app.include_router(comparisons.router, prefix="/api/v1")
app.include_router(mappings.router, prefix="/api/v1")
app.include_router(operators.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
