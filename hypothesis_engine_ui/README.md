# Hypothesis Engine UI

The web dashboard for Hypothesis Engine. It displays hypotheses, evidence,
insights, agent activity, and prediction-quality metrics from a separately
running Hypothesis Engine API.

## Requirements

- Node.js 24 or newer
- npm 11 or newer
- A running Hypothesis Engine API and a workspace API key

## Local development

Install dependencies and create a local environment file:

```bash
npm ci
cp .env.example .env.local
```

Set `HYPOTHESIS_API_URL` to the URL of your API, including its
`/api/v1` prefix:

```dotenv
HYPOTHESIS_API_URL=http://localhost:8000/api/v1
```

This is trusted server configuration. Browser requests always go to `/api/v1`
on the UI origin. The server forwards them only to this configured upstream;
requests cannot choose another destination. Never put a key in the URL or any
`NEXT_PUBLIC_*` variable. The server proxy does not require browser CORS access
to the backend.

Start the development server:

```bash
npm run dev
```

Open <http://localhost:3000>, paste a workspace API key into **Open your
workspace**, and submit it. The UI verifies the key before saving it to that
browser's local storage. Disconnecting the workspace removes it.

## Production build

Set `HYPOTHESIS_API_URL` in the build and runtime environment, then build and run the
application:

```bash
npm ci
npm run build
npm start
```

Production requires an HTTPS upstream. Rebuild and restart when changing the
upstream so documentation redirects and API requests remain consistent. The
proxy forwards the workspace `X-API-Key`, method, query, body and API status.
It drops cookies and unrelated credentials, rejects off-origin redirects, and
marks all API responses private/no-store. No server workspace or master key is
configured in the UI.

The hosted UI is [hypothesis-md.vercel.app](https://hypothesis-md.vercel.app).
Its separate Vercel project uses `HYPOTHESIS_API_URL=https://hypothesis.md/api/v1`.
The existing `hypothesis.md` API hostname and database are unchanged. `SKILL.md`
and its relative reference links are served through the same proxy; `/docs`
redirects to the API documentation. See [UI release notes](../docs/MINIMAL-UI.md).

## Checks

```bash
npm test
npm run typecheck
npm run lint
npm run build
npm audit
```

Generated API types live in `types/api.d.ts`. Refresh them only after the API
contract has been reviewed:

```bash
npm run typegen:file
```
