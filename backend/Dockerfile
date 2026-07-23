# =============================================================================
# FGA CRM - Backend Dockerfile (build reproductible via uv + uv.lock)
# =============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv depuis PyPI, version pinnee (build reproductible).
RUN pip install --no-cache-dir uv==0.11.31

WORKDIR /app

# Deps runtime FIGEES depuis uv.lock dans /app/.venv (--no-dev exclut le groupe dev).
# App non-packagee (package=false) -> deps seules, l'app tourne en place.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# .venv/bin sur le PATH -> alembic / uvicorn / celery de l'entrypoint resolvent.
ENV PATH="/app/.venv/bin:$PATH"

# Copy application (le .venv local et les caches sont exclus par .dockerignore).
COPY . .

# S'assurer que l'entrypoint est executable (au cas ou COPY perdrait le bit).
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
