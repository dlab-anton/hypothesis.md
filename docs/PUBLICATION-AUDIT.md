# Public source audit — 14 September 2026

This is a bounded source and local verification audit, not a penetration-test
certificate or an attestation of a hosted environment.

## Source and publication boundary

The release was curated from the main Hypothesis Engine working checkout,
including its merged workspace authorization, context, and cap3 writeback work.
Adjacent baseline and writeback worktrees were older development stages; the
rollout directory held operational artifacts. The original checkout, uncommitted
work, Git history, research data, and existing private origin were preserved.

The public repository starts a new Git history. It excludes prior `.git` content,
local environments, credentials, deployment IDs/receipts, private smoke and
rollout automation, conversation archives, copied agent tooling, and legacy setup
guides. Historical capability artifacts are retained because integrations pin
their exact bytes. Source fingerprints are not Git history or credentials.

This source has security and dependency changes that have not been deployed by
the publication task. It must not be treated as an exact copy of a running
Hypothesis.md service or substituted into an existing Motive sender policy.

## Reviewed areas and changes

| Area | Finding and disposition |
| --- | --- |
| Browser credentials | Removed build-time public API-key fallback and unsafe master-key setup instructions. Only a user-supplied workspace key belongs in the dashboard. |
| Server configuration | Known placeholder and short master keys now fail startup in all environments. Validation errors hide input values. |
| Logging | Disabled SQL echo, hide bound SQL values, and log exception classes without database/exception contents. Hosting logs remain operator responsibility. |
| Tenant authorization | Reviewed endpoint-to-query scoping, key issuance/list/revocation, relationships, context reads, and cross-workspace denial. A workspace UUID alone cannot authorize additional key issuance. |
| Authentication compatibility | FastAPI's newer missing-key default changed from 403 to 401. An explicit header subclass preserves the established 403 API behavior; invalid keys remain 401. |
| Rate limits | Key issuance uses the ASGI peer rather than arbitrary forwarded headers, and the in-memory table now has a hard size bound. Distributed abuse control remains external. |
| Writeback | Preserved cap3 domain implementation and historical artifacts. Added `Idempotency-Key` to allowed CORS headers. Separate publication artifact records the dependency-induced OpenAPI validation-error schema change. |
| Database and RLS | Migrations work on PostgreSQL but do not install Supabase RLS policies. Self-hosting instructions require closing alternate Data API access before migration/data use. No live grants, schema, Auth, or storage changes were made. |
| External access and storage | The API stores structured PostgreSQL records; evidence source strings are not fetched as URLs. No file-upload/object-storage subsystem is implemented. No model execution or automatic model billing is implemented. |
| Dependencies | Initial npm audit reported 13 affected packages; initial Python runtime audit reported 21 advisory entries across 5 packages (including duplicate IDs). A separate development scan found an affected pytest version. Patched lockfiles replace the affected versions. |
| Licensing | Project-authored source is MIT licensed. Adapted shadcn/ui components retain the upstream MIT notice. Dependency packages retain their own licenses and are not vendored. |
| CI | Uses pinned action commits, read-only repository permissions, no persisted checkout credential, bounded jobs, immutable runtime export checking, and a fresh UUID database runner. |

## Test-fixture repairs

The first broad local API run passed 455 tests and exposed 37 failures. Four were
the dependency's missing-key status change, fixed compatibly in application code.
The existing tenancy fixtures installed competing global authentication overrides,
so both clients could run as the last tenant configured. They now use real hashed
workspace keys through the normal authentication path.

Other legacy success-case fixtures omitted the already-required conclusion
outcome, expected an old channel spelling/self-reference status, or sent an
evidence payload without its required type. Those fixtures were corrected to the
existing API contract. Negative outcome/authorization cases remain covered; no
tests were skipped to obtain a passing result.

## Verification evidence

- Fresh pinned Python 3.12 test environment installed from the exported lockfile.
- PostgreSQL migration to 017, downgrade to 016, and re-upgrade passed on a newly
  created UUID database. The runner removed only its own database afterward.
- After the fixture repairs, all 14 real-key tenancy cases passed. Nine focused
  configuration/redaction/issuance tests also passed.
- The final complete API run passed **493 tests, zero skips**, including real-key
  isolation, auth compatibility, context snapshots, replay/channel races,
  historical cap3 domain fingerprint compatibility, and publication security.
- Python syntax/undefined-name lint and lockfile consistency checks passed.
- Updated pinned Python runtime and development dependencies: `pip-audit`
  reported no known vulnerabilities. The complete 493-test suite also passed
  with the patched pytest 9.0.3 runner.
- Curated source scan with Gitleaks 8.30.1 reported no secrets. Four initial
  findings were literal sample curl headers, replaced by environment-variable
  examples rather than scanner suppressions.

- Frontend: 14 unit tests, lint, TypeScript, production build, and generated API
  types passed; npm audit reported zero vulnerabilities.
- Browser checks against a controlled API stub passed: no-key landing made zero
  API requests; invalid/503 keys were not stored; a valid key connected to the
  board without appearing in page markup. An existing key encountering 503
  retained retry access while protected board content stayed hidden. No error
  overlay appeared. Production CSP omitted `unsafe-eval`.

Browser integration used a controlled stub, while real backend authorization and
data behavior were exercised separately against PostgreSQL. Public CI status is
available on the repository's Actions page. Audit results are a point-in-time
view; dependency advisories and hosting settings can change.

## Live-check and security limits

A bounded anonymous request to `https://hypothesis.md` returned a 49-byte API root
document with no script assets. That document had no exact match to the locally
available master/public-key comparison values. No credential values were logged,
published, or used for authenticated requests. This does not verify a separate
frontend deployment, the current hosted environment, or absence of historical
credential exposure. No credential rotation was inferred from this check.

There is no independent member-role system, verified actor identity, expected
hypothesis revision, or external conclusion-review authority. Workspace members
can issue independent keys; only the server master can revoke keys. Browser local
storage carries the usual same-origin script risk. Application tenant scoping
does not protect an independently exposed database API. Rate limits are local to
one process. Backups, ingress controls, production load behavior, hosted RLS,
storage, billing, and live deployment regression testing were not verified.

No Docker image build, production write, live migration, deployment, credential
mutation, research cleanup, or history rewrite of the original repository was
performed as part of this release preparation.
