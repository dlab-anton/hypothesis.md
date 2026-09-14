# Motive shared-memory contract

Hypothesis.md is the receiver for structured hypotheses, evidence, and insights.
Motive controls whether an observation is authorized for delivery. Publishing or
deploying this receiver grants no research acceptance, owner approval, spending
authority, or automatic writeback permission.

The `contracts/` files under `hypothesis_engine_api` retain historical versioned
capability artifacts used by integrations. Their source-baseline and overlay
labels are historical provenance, not claims that this public snapshot equals a
current production deployment. Do not silently replace a sender's pinned artifact.

The cap3 contract supports:

- `Idempotency-Key` on hypothesis, evidence, and insight creation, scoped to
  authenticated workspace and operation. A matching normalized payload returns
  the original 201 response; a changed payload returns 409. Authentication is
  evaluated on every request. Receipts have no expiry.
- Optional non-null `expected_channel_id` on new evidence. The receiver locks the
  tenant-scoped hypothesis and exact current channel identity before insertion.
  A mismatch returns 409 without a committed write. Omission retains historical
  request normalization.
- An identical replay after a channel move returns a historical receipt. It is
  not a claim about the target's current channel or revision.

Channel and hypothesis context endpoints build tenant-scoped read-only snapshots
for a caller's current workspace. Explicit resource IDs are checked within that
scope. Response fixtures are synthetic. Consumers must retain the distinction
between observations, conclusions, and approval authority.

There is no expected-revision/If-Match protection, verified actor attribution, or
independent conclusion-review endpoint. Send neutral observations without changing
confidence unless separate current authority explicitly permits otherwise.
`automatic_writeback_ready: false` is deliberate, not a feature toggle.

The exporter produces `motive-writeback-publication-017.json` for this source.
The dependency security update adds optional `input` and `ctx` properties to the
OpenAPI validation-error schema, changing its surface hash. The cap3 domain
implementation hashes remain unchanged. Tests verify the publication artifact
and its unchanged domain implementation against the historical cap3 artifact.
Do not substitute the publication artifact into an existing sender policy without
coordinated review. A public OpenAPI read alone cannot verify production writes.
