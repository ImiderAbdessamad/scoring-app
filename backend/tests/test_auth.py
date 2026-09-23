"""Vérification des access tokens Keycloak, avec une paire de clés RSA locale."""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import settings
from app.main import app

client = TestClient(app)

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-kid"


@pytest.fixture(autouse=True)
def _local_jwks(monkeypatch):
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key(), as_dict=True)
    jwk.update({"kid": _KID, "alg": "RS256", "use": "sig"})
    cache = security._JwksCache()
    cache._keys = {_KID: jwt.PyJWK(jwk)}
    cache._fetched_at = time.monotonic()
    monkeypatch.setattr(security, "_jwks", cache)
    monkeypatch.setattr(settings, "auth_enabled", True)


def _token(**overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": security.issuer(),
        "aud": [settings.keycloak_client_id, "account"],
        "azp": settings.keycloak_client_id,
        "sub": "9f7e1605-cbc2-427e-ad7e-10aca47392b7",
        "typ": "Bearer",
        "iat": now,
        "exp": now + 300,
        "name": "Test RCC1",
        "given_name": "Test",
        "family_name": "RCC1",
        "preferred_username": "test.rcc1",
        "email": "test.rcc1@rcc.local",
        "realm_access": {"roles": [settings.keycloak_required_role, "offline_access"]},
    }
    claims.update(overrides)
    claims = {key: value for key, value in claims.items() if value is not None}
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": _KID})


def _me(token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/api/v1/auth/me", headers=headers)


def test_valid_token_returns_user():
    response = _me(_token())
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "test.rcc1"
    assert body["display_name"] == "Test RCC1"
    assert body["initials"] == "TR"
    assert settings.keycloak_required_role in body["roles"]


def test_keycloak_clock_ahead_is_accepted():
    # Horloge Keycloak en avance sur le backend : `iat` dans le futur.
    now = int(time.time())
    assert _me(_token(iat=now + 120, exp=now + 420)).status_code == 200


def test_client_role_is_accepted():
    token = _token(
        realm_access={"roles": []},
        resource_access={settings.keycloak_client_id: {"roles": [settings.keycloak_required_role]}},
    )
    assert _me(token).status_code == 200


def test_missing_token_is_401():
    response = _me()
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_role_is_403():
    assert _me(_token(realm_access={"roles": ["offline_access"]})).status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 120},
        {"aud": ["account"]},
        {"iss": "https://keycloak.app-dev.wafabail.ma/realms/workflow_decision_wb"},
        {"typ": "ID"},
    ],
    ids=["expire", "mauvaise-audience", "autre-realm", "id-token"],
)
def test_rejected_tokens_are_401(overrides):
    assert _me(_token(**overrides)).status_code == 401


def test_foreign_signature_is_401():
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {"iss": security.issuer(), "aud": settings.keycloak_client_id, "sub": "x",
         "typ": "Bearer", "iat": int(time.time()), "exp": int(time.time()) + 300},
        other_key,
        algorithm="RS256",
        headers={"kid": _KID},
    )
    assert _me(token).status_code == 401


def test_rcc_routes_require_token():
    assert client.get("/api/v1/rcc/dossiers").status_code == 401
    assert client.get("/api/v1/rcc/audit").status_code == 401


def test_query_token_only_accepted_on_stream():
    token = _token()
    # Authentifié, puis 404 car le job n'existe pas.
    assert client.get(f"/api/v1/rcc/jobs/inconnu/stream?access_token={token}").status_code == 404
    assert client.get(f"/api/v1/rcc/audit?access_token={token}").status_code == 401


def test_health_routes_stay_public():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/rcc/health").status_code == 200


def test_auth_disabled_returns_dev_user(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    assert _me().json()["username"] == "dev"
