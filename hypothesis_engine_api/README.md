# Hypothesis.md API

FastAPI + SQLAlchemy + PostgreSQL. Start with the [root setup guide](../README.md).
The API is mounted at `/api/v1`; Swagger UI is at `/docs`.

Install the pinned runtime with `pip install -r requirements.txt`.
Poetry's lockfile also includes development dependencies:
`poetry install --no-root`. Run database checks through
`poetry run python scripts/test_database.py`, which creates and removes its own
UUID database on an existing loopback PostgreSQL instance.

Read [self-hosting](../docs/SELF-HOSTING.md) before exposing this service.
