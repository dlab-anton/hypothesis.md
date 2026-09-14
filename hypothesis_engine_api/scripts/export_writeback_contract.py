"""Export the LOCAL channel-conditioned HTTP write capability candidate.

No credentials or writes. --check-live checks the deployed public OpenAPI and
health; it does not claim to verify runtime write behavior in production.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The old local .env has a development version override. Use the deployment's
# explicit version, without changing the user's file or relabeling a live API.
os.environ.setdefault('APP_VERSION', '1.8.0')

from app.main import app

API_VERSION = '1.8.0'
BASE = 'https://hypothesis.md/api/v1'
CONTRACT_PATH = ROOT / 'contracts/motive-writeback-publication-017.json'
ROUTES = {
    '/api/v1/hypotheses': ('post',),
    '/api/v1/hypotheses/{hypothesis_id}': ('get', 'patch'),
    '/api/v1/hypotheses/{hypothesis_id}/evidence': ('get', 'post'),
    '/api/v1/hypotheses/{hypothesis_id}/revise': ('post',),
    '/api/v1/insights': ('get', 'post'),
    '/api/v1/insights/{insight_id}': ('get', 'patch'),
}


def surface(openapi):
    paths = {path: {method: openapi['paths'][path][method] for method in methods}
             for path, methods in ROUTES.items()}
    components = {}

    def visit(value):
        if isinstance(value, dict):
            if '$ref' in value:
                prefix, name = value['$ref'].rsplit('/', 1)
                assert prefix == '#/components/schemas', 'Unexpected external schema reference'
                if name not in components:
                    components[name] = openapi['components']['schemas'][name]
                    visit(components[name])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(paths)
    return {'paths': paths, 'components': {
        'schemas': components,
        'securitySchemes': openapi['components']['securitySchemes']}}


def contract():
    schema = app.openapi()
    if schema['info']['version'] != API_VERSION:
        raise ValueError('Local version differs from the pinned integration version')
    selected = surface(schema)
    digest = hashlib.sha256(json.dumps(selected, sort_keys=True,
                                      separators=(',', ':')).encode()).hexdigest()
    implementation_files = [
        'app/api/v1/endpoints/hypotheses.py', 'app/api/v1/endpoints/evidence.py',
        'app/api/v1/endpoints/insights.py', 'app/services/idempotency_service.py',
        'app/services/evidence_import_service.py',
        'app/db/models/idempotency.py', 'app/db/models/__init__.py',
        'app/schemas/common.py', 'app/schemas/hypothesis.py',
        'app/schemas/evidence.py', 'app/schemas/insight.py',
        'alembic/versions/017_write_idempotency.py',
    ]
    source_digests = {path: hashlib.sha256((ROOT / path).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
                      for path in implementation_files}
    return {
        'contract_version': 'hypothesis-http-writeback-capabilities/3',
        'api_version': API_VERSION,
        'source_baseline': '7546920632aa48107e6ec5f1b268f2b6d6a4be14',
        'source_overlay': 'public-source publication snapshot (not a deployment or sender admission)',
        'schema_revision': '017_write_idempotency',
        'automatic_writeback_ready': False,
        'surface_sha256': digest,
        'implementation_files_sha256': source_digests,
        'implementation_hash_encoding': 'UTF-8 source text with normalized LF line endings',
        'implementation_sha256': hashlib.sha256(json.dumps(
            source_digests, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'limitations': {
            'idempotency_key_enforced': True,
            'retry_returns_original_record': True,
            'changed_payload_with_same_key_conflicts': True,
            'expected_channel_id_enforced_for_new_evidence': True,
            'expected_revision_or_if_match_enforced': False,
            'authenticated_actor_attribution': False,
            'independent_conclusion_review': False,
            'assessment_or_review_route': False,
            'investigation_or_lease_route': False,
            'evidence_metadata_field': False,
            'tenant_id_is_public_identifier': False,
        },
        'idempotency': {
            'scope': ['authenticated_tenant', 'operation', 'Idempotency-Key'],
            'operations': ['hypotheses:create', 'evidence:create', 'insights:create'],
            'payload': 'SHA-256 of sorted UTF-8 JSON of the validated model including defaults; implicit initial_confidence resolved; evidence target UUID included in digest; expected_channel_id included only when provided',
            'success_status': 201,
            'changed_payload_status': 409,
            'key_pattern': '^[!-~]+$',
            'key_max_length': 200,
            'retention': 'No expiration; deleting replay records removes retry guarantees',
            'key_required': False,
            'actor_is_authorization': False,
        },
        'evidence_target_precondition': {
            'field': 'expected_channel_id',
            'required': False,
            'nullable': False,
            'new_write_mismatch_status': 409,
            'new_write_locking': 'The tenant-scoped hypothesis and exact current channel identity are locked before evidence insertion',
            'same_payload_replay_after_channel_move': True,
            'same_name_channel_replacement_rejected': True,
            'omitted_field_legacy_digest_compatible': True,
            'revision_semantics': 'Historical observation binding only; no current-revision assertion is implemented',
        },
        'verification_scope': 'LOCAL candidate only; atomic writes and migration tested in a runner-created UUID PostgreSQL database. Live runtime unchanged.',
        **selected,
    }


def check_live(local):
    import httpx
    with httpx.Client(timeout=30) as client:
        response = client.get(BASE + '/health')
        response.raise_for_status()
        if response.json() != {'status': 'ok', 'version': API_VERSION, 'database': 'ok'}:
            raise ValueError('Live health/version mismatch')
        response = client.get(BASE + '/openapi.json')
        response.raise_for_status()
        remote = response.json()
        if remote['info']['version'] != API_VERSION:
            raise ValueError('Live OpenAPI version mismatch')
        if surface(remote) != {key: local[key] for key in ('paths', 'components')}:
            raise ValueError('Live write route/schema drift; do not enable the adapter')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-live', action='store_true')
    parser.add_argument('--write', action='store_true',
                        help='Write the versioned local candidate contract file')
    args = parser.parse_args()
    result = contract()
    if args.check_live:
        check_live(result)
        print('PASS: public health and write schemas match the local candidate; this does not verify deployed write guarantees.')
    elif args.write:
        CONTRACT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(CONTRACT_PATH)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
