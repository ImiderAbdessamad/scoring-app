"""Authentification Keycloak : vérification locale des access tokens JWT du realm RCC.

Le backend n'appelle pas Keycloak à chaque requête : il télécharge les clés
publiques du realm (JWKS), les garde en cache, et vérifie signature, issuer,
audience et expiration localement.
"""
from __future__ import annotations

import logging
import threading
import time

import jwt
import requests
from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALGORITHMS = ["RS256"]
_LEEWAY_SECONDS = 30
# Un `kid` inconnu déclenche un rechargement (rotation des clés), au plus une fois par minute.
_JWKS_MIN_REFRESH_SECONDS = 60
_JWKS_TIMEOUT_SECONDS = 10

DEV_USER = {
    "id": "dev",
    "username": "dev",
    "display_name": "Développeur local",
    "email": None,
    "roles": [settings.keycloak_required_role],
    "initials": "DL",
}


def issuer() -> str:
    return f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"


def jwks_url() -> str:
    return settings.keycloak_jwks_url or f"{issuer()}/protocol/openid-connect/certs"


class _JwksCache:
    def __init__(self) -> None:
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = float("-inf")
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        response = requests.get(
            jwks_url(),
            timeout=_JWKS_TIMEOUT_SECONDS,
            verify=settings.keycloak_ca_bundle or True,
        )
        response.raise_for_status()
        # PyJWKSet ignore les clés inutilisables (ex. la clé de chiffrement RSA-OAEP).
        jwk_set = jwt.PyJWKSet.from_dict(response.json())
        self._keys = {key.key_id: key for key in jwk_set.keys if key.key_id}
        self._fetched_at = time.monotonic()
        logger.info("Clés Keycloak chargées depuis %s (%d clé(s))", jwks_url(), len(self._keys))

    def get(self, kid: str | None) -> jwt.PyJWK | None:
        with self._lock:
            if kid not in self._keys and (
                time.monotonic() - self._fetched_at >= _JWKS_MIN_REFRESH_SECONDS
            ):
                self._refresh()
            return self._keys.get(kid)


_jwks = _JwksCache()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    # EventSource ne peut pas envoyer d'en-tête : le flux SSE seul accepte le token en query.
    if request.url.path.endswith("/stream"):
        token = request.query_params.get("access_token", "").strip()
        if token:
            return token
    raise _unauthorized("Authentification requise.")


def _decode(token: str) -> dict:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError:
        raise _unauthorized("Jeton invalide.")
    try:
        key = _jwks.get(kid)
    except (requests.RequestException, jwt.PyJWTError, ValueError) as exc:
        logger.error("Clés Keycloak injoignables (%s) : %s", jwks_url(), exc)
        raise HTTPException(status_code=503, detail="Service d'authentification indisponible.")
    if key is None:
        raise _unauthorized("Jeton signé par une clé inconnue.")
    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=_ALGORITHMS,
            audience=settings.keycloak_client_id,
            issuer=issuer(),
            leeway=_LEEWAY_SECONDS,
            # `iat` n'est pas vérifié : l'horloge de Keycloak peut avancer sur la nôtre
            # (75 s constatées en dev) et un `iat` « futur » ne dit rien de la validité.
            # La durée de vie est portée par `exp`, toujours contrôlé.
            options={"require": ["exp", "iat", "iss", "aud", "sub"], "verify_iat": False},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expirée — reconnectez-vous.")
    except jwt.PyJWTError as exc:
        logger.info("Jeton refusé : %s", exc)
        raise _unauthorized("Jeton invalide.")
    # Un ID token porte la même audience : seul l'access token donne accès à l'API.
    if claims.get("typ") != "Bearer":
        raise _unauthorized("Jeton invalide.")
    return claims


def _roles(claims: dict) -> set[str]:
    roles = set(claims.get("realm_access", {}).get("roles", []))
    client = claims.get("resource_access", {}).get(settings.keycloak_client_id, {})
    roles.update(client.get("roles", []))
    return roles


def _initials(claims: dict, display_name: str) -> str:
    parts = [claims.get("given_name"), claims.get("family_name")]
    if not all(parts):
        parts = display_name.split()
    return "".join(part[0] for part in parts[:2] if part).upper()


def get_current_user(request: Request) -> dict:
    """Dépendance FastAPI : utilisateur authentifié portant le rôle RCC requis."""
    if not settings.auth_enabled:
        return DEV_USER
    claims = _decode(_extract_token(request))
    roles = _roles(claims)
    required = settings.keycloak_required_role
    if required and required not in roles:
        raise HTTPException(status_code=403, detail="Accès RCC non autorisé pour ce compte.")
    display_name = claims.get("name") or claims.get("preferred_username") or claims["sub"]
    return {
        "id": claims["sub"],
        "username": claims.get("preferred_username"),
        "display_name": display_name,
        "email": claims.get("email"),
        "roles": sorted(roles),
        "initials": _initials(claims, display_name),
    }
