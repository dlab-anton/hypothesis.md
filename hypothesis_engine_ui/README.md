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

Set `NEXT_PUBLIC_API_URL` to the public URL of your API, including its
`/api/v1` prefix:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

This value is included in browser code at build time, so it must be a public
URL. Do not put an API key, master key, or other secret in a `NEXT_PUBLIC_*`
variable. The API must allow requests from the dashboard origin when the two
services use different origins.

Start the development server:

```bash
npm run dev
```

Open <http://localhost:3000>, paste a workspace API key into **Connect this
dashboard**, and submit it. The UI verifies the key before saving it to that
browser's local storage. Disconnecting the workspace removes it.

## Production build

Set `NEXT_PUBLIC_API_URL` in the build environment, then build and run the
application:

```bash
npm ci
npm run build
npm start
```

Because `NEXT_PUBLIC_API_URL` is a build-time setting, rebuild the frontend
when the API URL changes. Serve both applications over HTTPS in production.
The frontend sends the locally stored workspace key in the `X-API-Key` header
only when calling the configured API.

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
