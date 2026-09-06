from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

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

class SpaStaticFiles(StaticFiles):
    """Static files with a single-page-app fallback.

    The UI routes on the client (``/analyze``, ``/explore``…), so a hard refresh or a
    shared deep link asks the server for a path that has no file behind it. Plain
    StaticFiles answers 404; serving ``index.html`` instead lets the router resolve it.

    The fallback deliberately stops at the API prefix. This mount sits at ``/``, so an
    unknown ``/api/v1/...`` path would otherwise fall through and answer 200 with the
    SPA shell — turning a missing endpoint into HTML that an API client cannot parse.
    """

    def __init__(self, *args: Any, api_prefix: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Paths reaching get_response are relative to the mount, so drop the slash.
        self._api_prefix = api_prefix.strip("/")

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            is_api_path = self._api_prefix != "" and (
                path == self._api_prefix or path.startswith(f"{self._api_prefix}/")
            )
            if exc.status_code == 404 and not is_api_path:
                return await super().get_response("index.html", scope)
            raise


# Serve the built frontend (SPA) when present, so a single process can host both the
# API and the UI in production. Skipped in dev/CI where the build does not exist.
_frontend_dist = Path(settings.frontend_dist_dir)
if _frontend_dist.is_dir():
    app.mount(
        "/",
        SpaStaticFiles(
            directory=_frontend_dist, html=True, api_prefix=settings.api_prefix
        ),
        name="frontend",
    )
