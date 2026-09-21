# Stage 1: Build frontend
FROM --platform=$BUILDPLATFORM node:26.9.0-alpine3.23@sha256:9dac39bfd053b458593c44a099d2667994c8fa9e1a8c10bc7ff2f3d97b62412d AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-progress
COPY frontend/ ./
RUN npm run build --silent 2>/dev/null

# Stage 2: Python runtime
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033
WORKDIR /app

# Install curl for health checks and uv for dependency management
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /uvx /usr/local/bin/

# Create the runtime user before copying application files so dependency and
# application layers are owned without a recursive ownership pass.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown appuser:appuser /app
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
USER appuser

# Copy Python project files for dependency installation
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install external dependencies first (cached)
RUN uv sync --locked --no-dev --no-install-project --quiet

# Copy source code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser server/ ./server/

# Final sync to install the project itself
RUN uv sync --locked --no-dev --quiet

# Copy built frontend to server static directory
COPY --chown=appuser:appuser --from=frontend-builder /app/frontend/build ./server/static/

# Expose the default port
EXPOSE 8000

# Set default environment variables
ENV HBC_SERVER_HOST=0.0.0.0
ENV HBC_SERVER_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/version || exit 1

# Run the server
CMD ["uv", "run", "--no-sync", "python", "-m", "server.app"]
