# Minimal web UI

The web app at https://hypothesis-md.vercel.app provides a workspace connection,
flat research rows, search and status/channel filters, paginated hypotheses,
retained insights, and readable evidence, timeline and lineage views. It uses
the existing Hypothesis API at https://hypothesis.md/api/v1. Research is private
to the connected workspace; the app does not offer anonymous research browsing.

The separate Vercel `hypothesis-md` project deploys `hypothesis_engine_ui`.
Set `HYPOTHESIS_API_URL=https://hypothesis.md/api/v1` for this hosted deployment.
Self-hosters may configure another trusted HTTPS API. The server validates the
URL and never selects an upstream from a request. Browser calls always use
`/api/v1`; cookie and authorization headers are not forwarded. Workspace keys
are supplied only by the browser's local storage, in `X-API-Key`. Responses are
streamed with their API status and marked private/no-store. Redirects stay within
the configured API's `/api/v1` prefix.

The frontend release does not deploy the API source, run migrations, modify
research, rotate keys or change the Motive writeback contract. No model executes
and no model billing starts when connecting the UI.

Verification covers the frontend build, lint, TypeScript, focused auth/filter/
proxy tests, and browser interactions with explicitly synthetic local fixtures.
Live unauthenticated checks cover API denial and linked agent documents. This
release does not claim a live authenticated research-data test.
