# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install uv for dependency management
RUN pip install uv

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY server/ ./server/

# Install Python dependencies
RUN uv sync --no-dev

# Copy built frontend to server static directory
COPY --from=frontend-builder /app/frontend/build ./server/static/

# Expose the default port
EXPOSE 8000

# Set default environment variables
ENV HBC_SERVER_HOST=0.0.0.0
ENV HBC_SERVER_PORT=8000

# Run the server
CMD ["uv", "run", "python", "-m", "server.app"]

