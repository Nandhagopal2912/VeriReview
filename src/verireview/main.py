"""FastAPI application factory.

Run locally with:  uv run uvicorn verireview.main:app --reload
"""

import logging

from fastapi import FastAPI

from verireview import __version__
from verireview.api.health import router as health_router
from verireview.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(title="VeriReview", version=__version__)
    app.include_router(health_router)
    return app


app = create_app()
