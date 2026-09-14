#!/bin/bash
set -e

# Render provides DATABASE_URL as postgresql:// but asyncpg needs postgresql+asyncpg://
if [[ "$DATABASE_URL" == postgresql://* ]]; then
  export DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgresql://}"
fi

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting HypothesisEngine API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
