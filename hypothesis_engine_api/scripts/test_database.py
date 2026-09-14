"""Migrate and test a fresh UUID database on an existing loopback PostgreSQL.

Set HYPOTHESIS_TEST_ADMIN_URL to the administrative postgres database URL.
No existing application/test database is modified. No Docker images are built.
"""
import asyncio
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid

import asyncpg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


async def run() -> int:
    admin_url = make_url(os.environ.get(
        "HYPOTHESIS_TEST_ADMIN_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
    ))
    if admin_url.host not in {"localhost", "127.0.0.1", "::1"} or admin_url.database != "postgres":
        raise RuntimeError("Test administration must target the postgres database on loopback")
    database = "hypothesis_writeback_" + uuid.uuid4().hex
    admin = await asyncpg.connect(
        host=admin_url.host, port=admin_url.port or 5432,
        user=admin_url.username, password=admin_url.password, database="postgres",
    )
    created = False
    try:
        await admin.execute(f'CREATE DATABASE "{database}"')
        created = True
        url = admin_url.set(drivername="postgresql+asyncpg", database=database).render_as_string(hide_password=False)
        env = {**os.environ, "DATABASE_URL": url, "TEST_DATABASE_URL": url,
               "ALEMBIC_DATABASE_URL": url, "ENVIRONMENT": "production",
               "APP_VERSION": "1.8.0", "API_MASTER_KEY": secrets.token_hex(32)}
        print("Created a fresh UUID database for migrations and tests.", flush=True)
        for args in (["upgrade", "head"], ["downgrade", "016_initial_confidence"], ["upgrade", "head"]):
            result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
        return subprocess.run(
            [sys.executable, "-m", "pytest", *(sys.argv[1:] or ["tests"]), "-q", "-ra"],
            cwd=ROOT, env=env,
        ).returncode
    finally:
        if created:
            await admin.execute(f'DROP DATABASE "{database}" WITH (FORCE)')
            print("Dropped only the UUID database created by this runner.", flush=True)
        await admin.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
