"""Main FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from src.server.routes_health import router as health_router
from src.server.routes_tools import router as tools_router
from src.server.routes_webhooks import router as webhooks_router
from src.dograh.workflow_builder import export_workflow_files
from src.utils.logger import get_logger

logger = get_logger("fastapi_app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode.")
    # Auto-export Dograh workflow JSON files on startup
    try:
        export_workflow_files(base_url=settings.WEBHOOK_BASE_URL)
        logger.info("Auto-generated Dograh workflow JSON blueprints in workflows/")
    except Exception as exc:
        logger.warning(f"Could not export workflow files on startup: {exc}")
    yield
    logger.info("Shutting down Voice AI Agent Service.")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="AI Voice Agent Service (Dograh, Cal.com & CRM)",
        description=(
            "Voice AI backend for inbound appointment booking and outbound BANT lead qualification. "
            "Integrates Dograh AI workflows, Cal.com real-time scheduling, and modular CRM adapters."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Route Blueprints
    app.include_router(health_router)
    app.include_router(tools_router)
    app.include_router(webhooks_router)

    return app


app = create_app()
