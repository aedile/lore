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


def create_app() -> FastAPI:
    """Build the FastAPI application instance.

    Returns:
        Configured FastAPI app with /health and metadata.
    """
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
