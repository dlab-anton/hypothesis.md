"""Synthetic local candidate guarantees and remaining compatibility limitations.

These assert the local migration-017 boundary so Motive cannot mistake an ignored
field/header for an implemented safety guarantee. Update with a versioned
contract when those guarantees are deliberately implemented.
"""
import uuid
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db_session
from app.api.v1.endpoints.keys import _rate_log
from app.main import app

BASE = '/api/v1'
ACTOR = 'synthetic-motive-evaluator'


def test_checked_in_contract_matches_generated_source():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, 'scripts/export_writeback_contract.py'],
        cwd=root, env={**os.environ, 'APP_VERSION': '1.8.0'},
        capture_output=True, text=True, check=True)
    expected = json.loads((root / 'contracts/motive-writeback-publication-017.json').read_text(encoding='utf-8'))
    generated = json.loads(result.stdout)
    assert generated == expected
    historical = json.loads((root / 'contracts/motive-writeback-channel-017.json').read_text(encoding='utf-8'))
    assert generated['implementation_sha256'] == historical['implementation_sha256']
    assert generated['contract_version'] == 'hypothesis-http-writeback-capabilities/3'
    precondition = generated['evidence_target_precondition']
    assert precondition == {
        'field': 'expected_channel_id',
        'required': False,
        'nullable': False,
        'new_write_mismatch_status': 409,
        'new_write_locking': 'The tenant-scoped hypothesis and exact current channel identity are locked before evidence insertion',
        'same_payload_replay_after_channel_move': True,
        'same_name_channel_replacement_rejected': True,
        'omitted_field_legacy_digest_compatible': True,
        'revision_semantics': 'Historical observation binding only; no current-revision assertion is implemented',
    }
    evidence_schema = generated['components']['schemas']['EvidenceCreate']
    expected_channel = evidence_schema['properties']['expected_channel_id']
    assert expected_channel['type'] == 'string'
    assert expected_channel['format'] == 'uuid'
    assert 'anyOf' not in expected_channel
    assert 'expected_channel_id' not in evidence_schema['required']
    evidence_post = generated['paths']['/api/v1/hypotheses/{hypothesis_id}/evidence']['post']
    assert evidence_post['responses']['409']['description'] == (
        'Target channel mismatch or conflicting keyed request'
    )


@pytest.fixture
async def authenticated(db_session):
    async def database():
        yield db_session

    app.dependency_overrides[get_db_session] = database
    _rate_log.clear()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://synthetic') as client:
            created = await client.post(BASE + '/keys', json={'label': 'SYNTHETIC contract test'})
            assert created.status_code == 201
            key = created.json()
            client.headers['X-API-Key'] = key['key']
            yield client, key
    finally:
        app.dependency_overrides.clear()
        _rate_log.clear()


async def hypothesis(client, **changes):
    response = await client.post(BASE + '/hypotheses', json={
        'statement': 'SYNTHETIC: a checked candidate does not establish method superiority.',
        'created_by': ACTOR, 'status': 'active', 'confidence': 0.4,
        'channel': 'synthetic-contract-only', **changes})
    assert response.status_code == 201
    return response.json()


def observation(**changes):
    return {'content': 'SYNTHETIC geometry validator accepted this fixture only.',
            'source': 'urn:synthetic:report:sha256:' + 'a' * 64,
            'evidence_type': 'neutral', 'created_by': ACTOR, **changes}


@pytest.mark.parametrize('resource', ['hypotheses', 'evidence', 'insights'])
async def test_duplicate_delivery_replays_and_changed_payload_conflicts(authenticated, resource):
    client, _ = authenticated
    path = BASE + '/' + resource
    payload = {'statement': 'SYNTHETIC duplicate request', 'created_by': ACTOR}
    if resource == 'evidence':
        h = await hypothesis(client)
        path = BASE + f"/hypotheses/{h['id']}/evidence"
        payload = observation()
    elif resource == 'insights':
        payload = {'channel': 'synthetic', 'insight_type': 'pattern',
                   'content': 'SYNTHETIC unreviewed interpretation', 'created_by': ACTOR}
    # The first call commits, but the caller discards the response before retry.
    first = await client.post(path, json=payload, headers={'Idempotency-Key': 'synthetic-delivery'})
    replay = await client.post(path, json=payload, headers={'Idempotency-Key': 'synthetic-delivery'})
    changed = {**payload, ('statement' if resource == 'hypotheses' else 'content'): 'SYNTHETIC changed payload'}
    conflict = await client.post(path, json=changed, headers={'Idempotency-Key': 'synthetic-delivery'})
    assert (first.status_code, replay.status_code, conflict.status_code) == (201, 201, 409)
    records = [r.json()['evidence'] if resource == 'evidence' else r.json()
               for r in (first, replay)]
    assert len({r['id'] for r in records}) == 1
    assert first.json() == replay.json()


async def test_evidence_preserves_source_actor_and_does_not_conclude(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    payload = observation()
    response = await client.post(BASE + f"/hypotheses/{h['id']}/evidence", json=payload)
    assert response.status_code == 201
    record = response.json()
    assert record['evidence']['source'] == payload['source']
    assert record['evidence']['created_by'] == ACTOR
    assert record['evidence']['confidence_after'] == 0.4
    assert record['hypothesis']['status'] == 'active'
    assert record['hypothesis']['confidence'] == 0.4
    insights = await client.get(BASE + '/insights')
    assert insights.json()['total'] == 0


async def test_evidence_confidence_is_an_optional_mutation(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    response = await client.post(BASE + f"/hypotheses/{h['id']}/evidence",
                                 json=observation(confidence=0.9))
    assert response.status_code == 201
    assert response.json()['hypothesis']['confidence'] == 0.9
    assert response.json()['hypothesis']['status'] == 'active'


async def test_unknown_evidence_metadata_and_delivery_fields_are_ignored(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    response = await client.post(BASE + f"/hypotheses/{h['id']}/evidence", json=observation(
        metadata={'report_digest': 'synthetic'}, idempotency_key='synthetic', expected_revision=999))
    assert response.status_code == 201
    evidence = response.json()['evidence']
    assert not {'metadata', 'idempotency_key', 'expected_revision'} & evidence.keys()


async def test_stale_revision_and_if_match_do_not_prevent_overwrite(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    path = BASE + f"/hypotheses/{h['id']}"
    current = await client.patch(path, json={'statement': 'SYNTHETIC newer statement', 'created_by': ACTOR})
    assert current.status_code == 200
    stale = await client.patch(path, json={'statement': 'SYNTHETIC stale overwrite',
        'expected_revision': -1, 'created_by': ACTOR}, headers={'If-Match': '"stale"'})
    assert stale.status_code == 200
    assert stale.json()['statement'] == 'SYNTHETIC stale overwrite'
    assert 'revision' not in stale.json()


async def test_same_actor_can_conclude_without_independent_review(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    path = BASE + f"/hypotheses/{h['id']}"
    # Lifecycle constraints exist, but are not approval/independence checks.
    invalid = await client.patch(path, json={'status': 'supported', 'outcome': {'synthetic': True}})
    assert invalid.status_code == 409
    assert (await client.patch(path, json={'status': 'testing', 'created_by': ACTOR})).status_code == 200
    missing = await client.patch(path, json={'status': 'supported', 'created_by': ACTOR})
    assert missing.status_code == 422
    concluded = await client.patch(path, json={'status': 'supported', 'created_by': ACTOR,
        'outcome': {'result': 'SYNTHETIC only, not an independent review'}})
    assert concluded.status_code == 200
    assert concluded.json()['status'] == 'supported'


async def test_cross_tenant_writes_denied_and_unauthenticated_writes_denied(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    other = await client.post(BASE + '/keys', json={'label': 'SYNTHETIC other tenant'})
    client.headers['X-API-Key'] = other.json()['key']
    for method, path, payload in [
        ('post', f"/hypotheses/{h['id']}/evidence", observation()),
        ('patch', f"/hypotheses/{h['id']}", {'status': 'testing'}),
    ]:
        response = await client.request(method, BASE + path, json=payload)
        assert response.status_code == 404
    del client.headers['X-API-Key']
    denied = await client.post(BASE + '/hypotheses', json={'statement': 'SYNTHETIC', 'created_by': ACTOR})
    assert denied.status_code in (401, 403)


async def test_existing_tenant_key_issuance_requires_same_tenant_authority(authenticated):
    client, original = authenticated
    del client.headers['X-API-Key']
    body = {'tenant_id': original['tenant_id'], 'label': 'SYNTHETIC authorized child'}
    denied = await client.post(BASE + '/keys', json=body)
    assert denied.status_code == 403
    assert denied.headers['Cache-Control'] == 'no-store'
    client.headers['X-API-Key'] = original['key']
    joined = await client.post(BASE + '/keys', json=body)
    assert joined.status_code == 201
    assert joined.json()['tenant_id'] == original['tenant_id']
    assert joined.json()['key'] != original['key']


async def test_actor_is_declared_not_bound_to_the_key(authenticated):
    client, _ = authenticated
    h = await hypothesis(client, created_by='a-different-declared-actor')
    assert h['created_by'] == 'a-different-declared-actor'
    invalid = await client.post(BASE + '/hypotheses', json={
        'statement': 'SYNTHETIC slash attribution', 'created_by': 'motive/evaluator'})
    assert invalid.status_code == 422


async def test_no_assessment_review_or_lease_surface(authenticated):
    client, _ = authenticated
    schema = app.openapi()
    assert not any(word in path for path in schema['paths']
                   for word in ('/assessments', '/reviews', '/conclusions', '/investigations', '/leases'))
    response = await client.post(BASE + '/conclusions/' + str(uuid.uuid4()) + '/review',
                                 json={'decision': 'approve'})
    assert response.status_code == 404


async def test_archived_evidence_is_rejected(authenticated):
    client, _ = authenticated
    h = await hypothesis(client)
    assert (await client.delete(BASE + f"/hypotheses/{h['id']}")).status_code == 200
    response = await client.post(BASE + f"/hypotheses/{h['id']}/evidence", json=observation())
    assert response.status_code == 409
