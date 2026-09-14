# Self-hosting

Use a dedicated PostgreSQL database, a server-only database login, and a randomly
generated master key. Set `ENVIRONMENT=production`, configure exact dashboard
origins in `CORS_ORIGINS`, terminate TLS at a trusted reverse proxy, and limit
network access to the database. Never expose a development server publicly.

The API uses custom workspace API keys, not Supabase Auth. All workspace members
have equivalent authority. Keep operational administration separate from normal
workspace access. Arrange secure key recovery/revocation procedures and backups;
the project does not provide email recovery or an administrator UI.

## PostgreSQL and Supabase

Plain PostgreSQL works without Supabase. If using Supabase as the database host,
disable the Data API for this project or place the application's tables in a
schema that is not exposed. Do this before running migrations or writing data.
The supplied migrations do not install RLS or `auth.uid()` policies, and the
application does not forward Supabase user JWTs to PostgreSQL.

When using a dedicated exposed schema is unavoidable, an administrator must
enable RLS on every application table and revoke direct access from public API
roles; do not add permissive policies to make the API work. Test both the FastAPI
server connection and anonymous/authenticated Data API denial. The server's
database owner connection is trusted and enforces workspace isolation in code.
New migrations must receive the same review before exposure.

Supabase defaults vary by project age. Grants and RLS are separate controls;
do not assume that a newly created table is private.
[Supabase's API security guide](https://supabase.com/docs/guides/api/securing-your-api)
explains the current controls. This source audit did not change or attest a live
Supabase project's grants, RLS, Auth configuration, or storage buckets.

## Reverse proxy and abuse controls

The key issuance limiter uses the ASGI client address. Configure Uvicorn's
`--proxy-headers` and `--forwarded-allow-ips` only for your actual trusted proxy
addresses; never trust arbitrary forwarded headers from the internet. Ensure the
proxy replaces client-supplied forwarding headers. Per-process limits reset on
restart and are not shared across workers or serverless instances.

Apply request-body limits, timeouts, and shared rate limits at ingress. Choose an
operator policy for public workspace creation (`POST /api/v1/keys` without a
workspace ID). A private deployment can restrict that route at ingress.

Database logs and application error responses omit query parameter values by
default. Review hosting access logs separately: infrastructure logging policies
are outside this repository.

## Deployment and upgrades

Build the frontend with its public API URL, then run `npm start`. Run the API with
Uvicorn and secrets from your host's secret store. Execute `alembic upgrade head`
as a deliberate deployment step with a database backup. Migration 017 stores
durable retry receipts; deleting these records removes replay guarantees.

`docker-compose.yml` is an optional local API/database setup and binds the API to
loopback. It requires an explicit master key. Its database password defaults are
local examples; configure independent credentials before broader use. Docker
images were not built during the publication audit.

`hypothesis_engine_api/vercel.json` is a generic API configuration. Link your own
project and secrets if using it; no account IDs or existing deployment links are
included. Configure database pooler/TLS options appropriate to your own host.

Keep the public repository, dependency updates, and hosted deployment as separate
review steps. Do not replace a live deployment solely because this snapshot has
newer dependency locks.
