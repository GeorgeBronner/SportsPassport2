# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend ./

# Build frontend
RUN npm run build

# Stage 2: Backend with static files
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy backend project files
COPY backend/pyproject.toml ./
COPY backend/college_football_tracker ./college_football_tracker
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/tests ./tests

# Copy built frontend from previous stage
COPY --from=frontend-builder /frontend/../backend/static ./static

# Install dependencies using uv
RUN uv pip install --system -e . && \
    uv pip install --system pytest pytest-asyncio

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn college_football_tracker.main:app --host 0.0.0.0 --port 8000"]
