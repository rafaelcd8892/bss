from fastapi import FastAPI

from baseball_sim.api.routes import router as api_router
from baseball_sim.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Deterministic sabermetrics-driven MLB simulation API.",
)
app.include_router(api_router, prefix=settings.api_prefix)
