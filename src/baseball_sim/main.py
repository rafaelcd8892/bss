from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from baseball_sim.api.routes import router as api_router
from baseball_sim.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Deterministic sabermetrics-driven MLB simulation API.",
)

_cors_origins = settings.cors_origin_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Credentials cannot be combined with a wildcard origin per the CORS spec.
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)

# Serve the built frontend (SPA) when present, so a single process can host both the
# API and the UI in production. Skipped in dev/CI where the build does not exist.
_frontend_dist = Path(settings.frontend_dist_dir)
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
