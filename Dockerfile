# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent --no-progress
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install curl for health checks, gosu for privilege drop, and uv for dependency management
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY server/ ./server/

# Install Python dependencies
RUN uv sync --no-dev --quiet

# Copy built frontend to server static directory
COPY --from=frontend-builder /app/frontend/build ./server/static/

# Create data directory and non-root user for security
RUN mkdir -p /data \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app /data

# Copy and setup entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose the default port
EXPOSE 8000

# Set default environment variables
ENV HBC_SERVER_HOST=0.0.0.0
ENV HBC_SERVER_PORT=8000
ENV HBC_DATA_DIR=/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/version || exit 1

# Entrypoint fixes permissions then drops to appuser
ENTRYPOINT ["docker-entrypoint.sh"]

# Run the server
CMD ["uv", "run", "python", "-m", "server.app"]
