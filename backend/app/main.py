"""LumenGrid FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import dataset, health, ml, nac, predictions, simulation, towers
from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.data_generator import seed_demo_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info(
        "Starting %s (env=%s, sandbox=%s)",
        settings.app_name,
        settings.app_env,
        settings.sandbox_mode,
    )
    init_db()
    db = SessionLocal()
    try:
        seed_result = seed_demo_dataset(db, force=False)
        logger.info("Demo seed: %s", seed_result)
    finally:
        db.close()
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "LumenGrid PoC — 5G traffic detection via Nokia Network as Code "
            "(CAMARA) signal scattering, without physical roadside sensors."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(nac.router)
    app.include_router(dataset.router)
    app.include_router(predictions.router)
    app.include_router(simulation.router)
    app.include_router(ml.router)
    app.include_router(towers.router)
    return app


app = create_app()
