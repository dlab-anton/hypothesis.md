import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.api.v1.endpoints import keys


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("key", ["REPLACE_ME_WITH_A_REAL_KEY", "generate-a-random-key-here", "short"])
def test_master_key_must_be_configured_in_every_environment(environment, key):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT=environment, API_MASTER_KEY=key)


def test_client_cannot_spoof_issuance_ip_with_a_forwarded_header():
    request = Request({"type": "http", "client": ("127.0.0.1", 1234),
                       "headers": [(b"x-forwarded-for", b"203.0.113.8")]})
    assert keys._get_client_ip(request) == "127.0.0.1"


def test_invalid_configuration_does_not_render_secrets():
    synthetic_secret = "synthetic-sensitive-value-for-error-redaction"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, API_MASTER_KEY=synthetic_secret,
                 DATABASE_URL="", CORS_ORIGINS=[])
    assert synthetic_secret not in str(error.value)


async def test_key_issuance_table_has_a_hard_bound(monkeypatch):
    monkeypatch.setattr(keys, "_MAX_IPS", 1)
    monkeypatch.setattr(keys, "_rate_log", {})
    await keys._check_rate_limit("first")
    with pytest.raises(HTTPException) as error:
        await keys._check_rate_limit("second")
    assert error.value.status_code == 429
    assert len(keys._rate_log) == 1


async def test_cors_allows_durable_writeback_header(client):
    response = await client.options("/api/v1/hypotheses", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-API-Key,Idempotency-Key,Content-Type",
    })
    assert response.status_code == 200
