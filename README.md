# Hypothesis.md

Structured shared memory for hypothesis-driven work. Record hypotheses, evidence,
confidence changes, relationships, and channel-level insights through a FastAPI
API and a Next.js dashboard.

Open the [web app](https://hypothesis-md.vercel.app) or read
[Skill.md](https://hypothesis-md.vercel.app/SKILL.md). The web app connects to the
existing API at `https://hypothesis.md/api/v1` using your workspace key.

Hypothesis.md records a research process. It does not establish that a claim is
true, verify an agent's identity, or replace independent scientific review.
It stores API data; it does not execute models, buy credits, or create model
billing automatically. Your hosting and independently connected agents have
their own costs.

## Run locally

Requires Python 3.12, Node.js 24, and an existing PostgreSQL 16 or newer database.
Use a dedicated empty database for your own installation.

```sh
git clone https://github.com/dlab-anton/hypothesis.md.git
cd hypothesis.md/hypothesis_engine_api
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated value in `API_MASTER_KEY` in `.env`, and set `DATABASE_URL` to
your PostgreSQL URL with the `postgresql+asyncpg://` scheme. The master key is
server administration authority: keep it out of browser configuration and use
workspace keys for normal work. Startup rejects missing, short, and known
placeholder master keys in every environment.

```sh
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd hypothesis.md/hypothesis_engine_ui
npm ci
cp .env.example .env.local
npm run dev
```

Open [the dashboard](http://localhost:3000) and
[API documentation](http://localhost:8000/docs). The frontend's server-side
`HYPOTHESIS_API_URL` defaults to `http://localhost:8000/api/v1`; browser requests
use its same-origin `/api/v1` proxy.

## Create a workspace

```sh
curl -X POST http://localhost:8000/api/v1/keys \
  -H 'Content-Type: application/json' \
  -d '{"label":"my-agent"}'
```

Save the returned `key` securely; it is shown once. Connect that workspace key in
the dashboard. API requests use the `X-API-Key` header. Creating a key for an
existing workspace requires a current key from that workspace or master
authority; a workspace UUID alone grants no access.

Workspace members share access and can issue additional workspace keys. They are
not separate roles. Only the server administrator can revoke keys. The dashboard
stores its workspace key in browser local storage, so use a trusted browser and
sign out on shared devices.

## Agents and Motive

The [agent guide](hypothesis_engine_api/SKILL.md) describes the API lifecycle.
[Motive integration](docs/MOTIVE-INTEGRATION.md) describes context snapshots,
atomic retry receipts, and channel preconditions. Hypothesis.md can be used
independently of [Motive.md](https://github.com/dlab-anton/motive.md).

## Development and deployment

See [development checks](docs/DEVELOPMENT.md),
[self-hosting](docs/SELF-HOSTING.md), and [security](SECURITY.md).
The [publication audit](docs/PUBLICATION-AUDIT.md) records scope, checks, and
remaining limits. A public source release does not change a hosted deployment.

This repository starts with a curated source snapshot and fresh Git history.
Operational credentials, deployment records, private research, and historical
conversations are not part of this distribution.

MIT licensed; third-party components retain their own licenses. See
[LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
