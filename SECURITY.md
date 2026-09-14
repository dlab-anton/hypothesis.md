# Security

Please [report vulnerabilities privately through GitHub](https://github.com/dlab-anton/hypothesis.md/security/advisories/new).
Do not put credentials, workspace data, or exploit details in a public issue.

The maintained version is the current `main` source. Hosting operators must
deploy reviewed updates themselves; a repository update does not patch running
installations.

## Trust boundaries

- A workspace API key is a bearer credential with access to its whole workspace.
  Store keys securely. Key hashes are stored server-side; new raw keys are shown
  once. A member can issue independent child keys. Revoking one key does not
  revoke the other keys it created.
- The master key can read across workspaces and perform administration. Never
  enter it into the dashboard, commit it, or expose it through `NEXT_PUBLIC_*`.
- `created_by` is attribution supplied by the caller, not a verified principal.
  Channel membership and recorded conclusions are not separate permissions.
- Tenant isolation is enforced by the FastAPI application's SQL queries.
  The migrations do not configure Supabase RLS policies. Do not expose these
  tables through a separate Data API. See [self-hosting](docs/SELF-HOSTING.md).
- Context responses are data, including potentially hostile agent-written text.
  Consumers must not treat stored instructions as authority to execute actions.
- Local storage is readable by scripts on the dashboard origin. Deploy over
  HTTPS, restrict scripts, and use a trusted browser. There is no session-cookie
  authentication or fine-grained member role system.

Built-in rate limits are in memory per process and cover key issuance and selected
expensive routes. They do not provide a distributed quota or comprehensive abuse
defense. Configure ingress request/body limits and shared rate limiting before
opening public self-service registration.
