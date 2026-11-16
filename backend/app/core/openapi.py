"""Métadonnées OpenAPI — documentation Swagger de l'API Wafabail."""

from __future__ import annotations

API_TITLE = "Wafabail Smart Dashboard API"
API_VERSION = "0.2.0"

API_DESCRIPTION = """
API de la plateforme **Wafabail Smart Dashboard** (crédit-bail).

Elle alimente le poste d'analyse scoring, le suivi des dossiers, l'analyse
sectorielle HCP, le copilote, et l'application RCC (liasse / conformité).

## Base URL

Toutes les routes métier sont sous **`/api/v1`**.  
Les sondes de santé sont à la racine (`/health`, `/health/live`, `/health/ready`).

En local, le frontend Vite (port 5173) **proxifie** `/api` vers le backend.

## Authentification

| Mécanisme | Où | Comment |
|---|---|---|
| **JWT Keycloak** (Bearer) | Scoring (`scoring-wb` / rôle `SCORING_USER`) | Header `Authorization: Bearer <access_token>` |
| **JWT Keycloak** (Bearer) | RCC (`rcc-wb` / rôle `RCC_USER`) | Idem, client et rôle RCC |
| **Clé API PVC** | `/partners/pvc/*` | Header `X-API-Key` (ou `Authorization: Bearer <clé>`) |
| **Mode local** | `AUTH_ENABLED=false` | Pas de jeton exigé — utilisateur de développement |

Dans Swagger, cliquez **Authorize** puis collez le jeton (sans le mot `Bearer`).

## Applications

- **Scoring** — dashboard, dossiers, analyse, secteurs, copilote.
- **RCC** — extraction de liasse, dossiers RCC, export, push bilans.
- **Partenaire PVC** — ingestion d'un dossier + liasse depuis pv-manager.

## Conventions

- Montants en **MAD** (affichage KDH côté UI).
- Identifiants dossier : `id` interne WFB (ex. préfixe dossier).
- Jobs d'analyse : créer un job, suivre `/analyse/jobs/{id}` ou le flux SSE `/stream`.
- Erreurs : JSON `{ "detail": "…" }` ; `X-Correlation-ID` sur chaque réponse.
"""

OPENAPI_TAGS = [
    {
        "name": "Santé",
        "description": "Sondes liveness / readiness (base, stockage, Kafka).",
    },
    {
        "name": "Tableau de bord",
        "description": "KPIs, file d'attente et alertes du poste scoring.",
    },
    {
        "name": "Dossiers",
        "description": (
            "Cycle de vie d'un dossier scoring : création, détail, documents, "
            "décision (approuver / réserver / rejeter), mémos, contrôles BAM / incidents, "
            "analyse sectorielle rattachée."
        ),
    },
    {
        "name": "Analyse scoring",
        "description": (
            "Pipeline OCR / ratios / score. Jobs asynchrones, état d'analyse, "
            "synthèse, copilote, extraction d'identité sur un PDF."
        ),
    },
    {
        "name": "Secteurs",
        "description": "Catalogue de sources sectorielles, branches HCP, rafraîchissement.",
    },
    {
        "name": "Données sectorielles",
        "description": "Synchronisation des jeux HCP / data.gov.ma et statut du cache.",
    },
    {
        "name": "Partenaire PVC",
        "description": (
            "API machine-to-machine pour pv-manager : dépôt d'un dossier + liasse, "
            "consultation par `noDemande`. Protégée par `PVC_API_KEY`."
        ),
    },
    {
        "name": "RCC",
        "description": (
            "Application RCC : jobs d'extraction, dossiers liasse, conformité, "
            "export, rapprochement client, envoi des bilans."
        ),
    },
    {
        "name": "RCC session",
        "description": "Profil de l'utilisateur Keycloak connecté à RCC (`GET /auth/me`).",
    },
]


def apply_security_schemes(schema: dict) -> dict:
    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Access token Keycloak. Client **scoring-wb** pour le dashboard / dossiers / analyse ; "
                "client **rcc-wb** pour `/rcc` et `/auth`. Inutile si `AUTH_ENABLED=false`."
            ),
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Clé partenaire PVC (`PVC_API_KEY`). Routes `/api/v1/partners/pvc/*`.",
        },
    }
    schema["servers"] = [
        {"url": "/", "description": "Même origine que l'UI (proxy Vite ou nginx)"},
    ]
    for path, methods in schema.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            if path.startswith("/api/v1/partners/pvc"):
                operation["security"] = [{"ApiKeyAuth": []}]
            elif path.startswith("/health"):
                operation["security"] = []
            elif path.startswith("/api/v1"):
                operation["security"] = [{"BearerAuth": []}]
    return schema
