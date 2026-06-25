FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install playwright system deps
RUN pip install --no-cache-dir playwright && playwright install-deps chromium

COPY pyproject.toml .
# Install all dependencies (non-editable — src is mounted as volume in dev)
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings httpx playwright apscheduler tenacity \
    python-dotenv structlog rapidfuzz beautifulsoup4 lxml \
    pytest pytest-asyncio pytest-cov ruff mypy

RUN playwright install chromium

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
