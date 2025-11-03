# syntax=docker/dockerfile:1.7

############################
# Base image
############################
FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    DATA_DIR=/data

# Install system deps (curl for healthcheck, tzdata optional)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}

# Copy dependency file first for layer caching
COPY requirements.txt ./

# Create a virtual environment (optional but keeps global clean)
# Could also just pip install into system site packages; using venv for clarity
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install -r requirements.txt

# Copy application code
COPY app ./app
COPY docs ./docs
COPY scripts ./scripts
COPY SETTINGS.md ./

# Create user and set ownership of app directory only
# (DATA_DIR will be bind-mounted with host permissions)
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home ${APP_HOME} appuser \
    && chown -R appuser:appgroup ${APP_HOME}

USER appuser

EXPOSE 8000

# Healthcheck uses the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Entrypoint / command
# Use exec form to get proper signal handling
CMD ["/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
