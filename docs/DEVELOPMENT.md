# Development checks

Python 3.12 and Node.js 24 are used by CI. Python runtime dependencies are pinned
in `requirements.txt`; `poetry.lock` also locks development tools.

```sh
cd hypothesis_engine_api
poetry install --no-root
poetry run python scripts/test_database.py
```

The runner connects to an existing loopback PostgreSQL administration database
named `postgres`, creates its own `hypothesis_writeback_<uuid>` database, applies
migrations, checks the 017 downgrade/upgrade, runs tests, and drops only the
database it created. Set `HYPOTHESIS_TEST_ADMIN_URL` in your local environment to
configure that connection. Its default is a local example with user/password
`postgres`. Never set it to an application database or shared test database.

To select tests, append pytest paths/options to the runner. For schema-only tests,
set a random `API_MASTER_KEY` and run `poetry run pytest tests/test_schemas.py
tests/test_constants.py`; application import validates configuration even when no
database is used.

```sh
cd hypothesis_engine_ui
npm ci
npm run lint
npx tsc --noEmit
npm run build
npm audit
```

Contract fixtures are intentional integration pins. Review contract changes with
the sender before replacing an artifact. Generated frontend API types must match
their checked-in OpenAPI document.
