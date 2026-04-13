# Stage 1: Build frontend
FROM --platform=$BUILDPLATFORM node:25-alpine@sha256:ad82ecad30371c43f4057aaa4800a8ed88f9446553a2d21323710c7b937177fc AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --silent --no-progress 2>/dev/null
COPY frontend/ ./
RUN npm run build --silent 2>/dev/null

# Stage 2: Python runtime
FROM python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab
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
