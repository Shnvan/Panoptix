# Pinned Python base image per ADR 0007
FROM python:3.12.7-slim AS base

# Security: non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --shell /bin/false appuser

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir uvicorn[standard]

# Copy application source
COPY src/ ./src/

# Security: non-root, read-only FS where possible
USER appuser

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "cctv_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
