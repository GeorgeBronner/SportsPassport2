FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY college_football_tracker ./college_football_tracker
COPY alembic ./alembic
COPY alembic.ini ./
COPY tests ./tests

# Install dependencies using uv
RUN uv pip install --system -e . && \
    uv pip install --system pytest pytest-asyncio

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn college_football_tracker.main:app --host 0.0.0.0 --port 8000"]
