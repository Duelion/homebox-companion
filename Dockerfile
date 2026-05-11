# Stage 1: Build frontend
FROM --platform=$BUILDPLATFORM node:26-alpine@sha256:e71ac5e964b9201072425d59d2e876359efa25dc96bb1768cb73295728d6e4ea AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --silent --no-progress 2>/dev/null
COPY frontend/ ./
RUN npm run build --silent 2>/dev/null

# Stage 2: Python runtime
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033
WORKDIR /app

# Install curl for health checks and uv for dependency management
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy Python project files for dependency installation
COPY pyproject.toml uv.lock ./

# Install external dependencies first (cached)
RUN uv sync --no-dev --no-install-project --quiet

# Copy source code
COPY src/ ./src/
COPY server/ ./server/

# Final sync to install the project itself
RUN uv sync --no-dev --quiet

# Copy built frontend to server static directory
COPY --from=frontend-builder /app/frontend/build ./server/static/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose the default port
EXPOSE 8000

# Set default environment variables
ENV HBC_SERVER_HOST=0.0.0.0
ENV HBC_SERVER_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/version || exit 1

# Run the server
CMD ["uv", "run", "python", "-m", "server.app"]
