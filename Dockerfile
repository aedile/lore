# =============================================================================
# lore-eligibility — Multi-stage Dockerfile
#
# Stage 1 (builder): Install Poetry and resolve all Python dependencies.
# Stage 2 (runtime): Copy installed packages from builder into a slim image.
#
# Security:
#   - Non-root user `lore` (UID 1000) in the runtime stage.
#   - No build tools or Poetry in the production image.
#   - EXPOSE 8000 (non-privileged port).
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — builder
# Install Poetry, resolve and install Python dependencies.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG POETRY_VERSION=2.2.1
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /build

# Copy lock files first — Docker layer caching skips reinstall on code changes.
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies only (no dev group).
RUN poetry config virtualenvs.in-project true \
    && poetry install --without dev --no-root --no-interaction --no-ansi

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# Minimal production image: Python 3.12 slim + installed packages + source.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Create a non-root user (UID 1000) to run the application.
RUN useradd --uid 1000 --no-create-home --shell /sbin/nologin lore

WORKDIR /app

# Copy the virtual environment from the builder stage.
COPY --from=builder /build/.venv /app/.venv

# Copy application source code and migration assets.
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY scripts/entrypoint.sh /app/entrypoint.sh

# Transfer ownership and ensure entrypoint is executable.
RUN chown -R lore:lore /app && chmod +x /app/entrypoint.sh

USER lore

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "lore_eligibility.bootstrapper.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
