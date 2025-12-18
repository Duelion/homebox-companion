# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent --no-progress 2>/dev/null
COPY frontend/ ./
RUN npm run build --silent 2>/dev/null

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install uv for dependency management and curl for health checks
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -q uv

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY server/ ./server/

# Install Python dependencies
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
