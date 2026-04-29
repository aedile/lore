"""FastAPI application factory and root entrypoint.

Run locally:
    poetry run uvicorn lore_eligibility.bootstrapper.main:app --reload

The app exposes a single /health endpoint at this stage. Domain routes
are added under bootstrapper/routers/ as modules come online (per the
ARD decomposition in Phase 02).
"""

from __future__ import annotations

from fastapi import FastAPI

from lore_eligibility import __version__
from lore_eligibility.bootstrapper.config_validation import validate_settings
from lore_eligibility.bootstrapper.logging_config import configure_logging
from lore_eligibility.bootstrapper.settings import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI application instance.

    Startup configuration validation is delegated to
    ``bootstrapper.config_validation.validate_settings``, which will
    raise ``ConfigurationError`` in staging or production if any
    insecure-config rule trips.

    Returns:
        Configured FastAPI app with /health and metadata.
    """
    settings = get_settings()

    # Fail fast on insecure config in staging / production. No-op in dev.
    validate_settings(settings)

    # Configure PII-redacting structured logging before any code path can
    # emit a log record. JSON output in non-dev environments; console
    # output for local readability.
    configure_logging(json_format=(settings.environment != "dev"))

    app = FastAPI(
        title="lore-eligibility",
        version=__version__,
        description="Eligibility data ingestion, cleansing, and identity verification.",
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe.

        Returns:
            Static status payload. A readiness probe with database
            connectivity will be added under bootstrapper/routers/ in a
            later phase.
        """
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
