"""Recherche client Wafabail (n° tiers) via l'API IA après extraction identité.

GET /ia-clients/search?rc=…&identifiantFiscal=…&ice=…
Utilise les champs déjà extraits de la 1ʳᵉ page de liasse (ICE / RC / IF).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.analyse import ClientLookup, IaClientMatch, ScoringAnalysisResult

logger = logging.getLogger(__name__)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"—", "-", "n/a", "N/A", "null", "None"}:
        return None
    return text


def _normalize_ice(value: str | None) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return raw
    if len(digits) < 15:
        digits = digits.zfill(15)
    return digits


def _normalize_rc(value: str | None) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    # Garde le numéro principal (avant /ville éventuelle).
    head = raw.split("/")[0].strip()
    digits = "".join(ch for ch in head if ch.isdigit())
    return digits or head


def _normalize_if(value: str | None) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or raw


def build_search_query(
    *,
    ice: str | None = None,
    rc: str | None = None,
    identifiant_fiscal: str | None = None,
) -> dict[str, str]:
    """Construit les query params selon les données disponibles (contrat API)."""
    params: dict[str, str] = {}
    ice_n = _normalize_ice(ice)
    rc_n = _normalize_rc(rc)
    if_n = _normalize_if(identifiant_fiscal)
    if ice_n:
        params["ice"] = ice_n
    if rc_n:
        params["rc"] = rc_n
    if if_n:
        params["identifiantFiscal"] = if_n
    return params


def _match_from_payload(item: dict[str, Any]) -> IaClientMatch:
    return IaClientMatch(
        ice=_clean(item.get("ice")),
        tiers=_clean(item.get("tiers")),
        rc=_clean(item.get("rc")),
        identifiant_fiscal=_clean(item.get("identifiantFiscal") or item.get("identifiant_fiscal")),
        raison_sociale=_clean(item.get("raisonSociale") or item.get("raison_sociale")),
    )


def search_ia_clients(
    *,
    ice: str | None = None,
    rc: str | None = None,
    identifiant_fiscal: str | None = None,
) -> ClientLookup:
    query = build_search_query(ice=ice, rc=rc, identifiant_fiscal=identifiant_fiscal)
    if not query:
        return ClientLookup(
            status="SKIPPED",
            query={},
            message="Aucun ICE, RC ou identifiant fiscal exploitable pour la recherche client.",
        )

    if not settings.ia_clients_enabled:
        return ClientLookup(
            status="SKIPPED",
            query=query,
            message="Recherche client IA désactivée (IA_CLIENTS_ENABLED=false).",
        )

    base = (settings.ia_clients_base_url or "").rstrip("/")
    if not base:
        return ClientLookup(
            status="SKIPPED",
            query=query,
            message="IA_CLIENTS_BASE_URL non configurée.",
        )

    url = f"{base}/ia-clients/search"
    headers: dict[str, str] = {"Accept": "application/json"}
    if settings.ia_clients_api_key:
        headers["X-API-Key"] = settings.ia_clients_api_key
        headers["Authorization"] = f"Bearer {settings.ia_clients_api_key}"

    try:
        with httpx.Client(timeout=settings.ia_clients_timeout_seconds) as client:
            response = client.get(url, params=query, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ia-clients/search HTTP %s query=%s body=%s",
            exc.response.status_code,
            query,
            (exc.response.text or "")[:300],
        )
        return ClientLookup(
            status="ERROR",
            query=query,
            message=f"API clients IA indisponible (HTTP {exc.response.status_code}).",
        )
    except Exception as exc:
        logger.warning("ia-clients/search failed query=%s error=%s", query, exc)
        return ClientLookup(
            status="ERROR",
            query=query,
            message=f"Recherche client IA impossible : {exc}",
        )

    rows = payload if isinstance(payload, list) else payload.get("items") or payload.get("data") or []
    if not isinstance(rows, list):
        rows = []
    matches = [_match_from_payload(item) for item in rows if isinstance(item, dict)]
    matches = [m for m in matches if m.tiers or m.ice or m.raison_sociale]

    if not matches:
        return ClientLookup(
            status="NOT_FOUND",
            query=query,
            matches=[],
            message="Aucun client trouvé pour les identifiants extraits.",
        )

    primary = matches[0]
    status = "MATCHED" if len(matches) == 1 else "MULTIPLE"
    return ClientLookup(
        status=status,
        query=query,
        matches=matches,
        primary=primary,
        message=(
            f"Client trouvé · n° tiers {primary.tiers}"
            if status == "MATCHED" and primary.tiers
            else f"{len(matches)} clients correspondants — vérifier le n° tiers."
        ),
    )


def enrich_result_with_ia_client(result: ScoringAnalysisResult) -> ScoringAnalysisResult:
    """Appelle l'API clients après extraction identité (ICE / RC / IF)."""
    identity = result.document.identity
    company = result.document.company
    lookup = search_ia_clients(
        ice=_pick(company.ice, identity.ice),
        rc=_pick(company.rc),
        identifiant_fiscal=_pick(identity.identifiant_fiscal, company.identifiant_fiscal),
    )
    result.client_lookup = lookup
    if lookup.primary and lookup.primary.tiers:
        logger.info(
            "Client IA matché tiers=%s ice=%s rc=%s",
            lookup.primary.tiers,
            lookup.primary.ice,
            lookup.primary.rc,
        )
    elif lookup.status not in {"SKIPPED"}:
        logger.info("Client IA status=%s query=%s", lookup.status, lookup.query)
    return result


def _pick(*values: Any) -> Any:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def client_lookup_to_workspace(lookup: ClientLookup | None) -> dict[str, Any] | None:
    if lookup is None:
        return None
    return lookup.model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /ia-clients/bilans (+ batch)
# ---------------------------------------------------------------------------

# Mapping postes RCC → champs API bilans Wafabail.
_BILAN_FIELD_MAP: dict[str, str] = {
    "capitauxPermanents": "FONDS_PROPRES",
    "actifsImmobilises": "ACTIFS_IMMOBILISES",
    "caAnnuelExport": "CA_EXPORT",
    "detteBancairesMlt": "DETTES_BANCAIRES_MLT",
    "detteBancairesCt": "DETTES_BANCAIRES_CT",
    "passifCirculant": "PASSIF_CIRCULANT",
    "dettesFournisseurs": "DETTES_FOURNISSEURS",
    "compteCourantAssocies": "COMPTE_COURANT_ASSOCIES",
    "tresoreriePassif": "TRESORERIE_PASSIF",
    "actifCirculant": "ACTIF_CIRCULANT",
    "creancesClients": "CREANCES_CLIENTS",
    "tresorerieActif": "TRESORERIE_ACTIF",
    "caisseActif": "CAISSE",
    "achatsRevendus": "ACHATS_REVENDUS",
    "achatsConsommes": "ACHATS_CONSOMMES",
    "autresChargesExternes": "AUTRES_CHARGES_EXTERNES",
    "chargesInterets": "CHARGES_INTERETS",
    "resultatNet": "RESULTAT_NET",
}


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_year(*candidates: Any) -> int | None:
    import re
    from datetime import datetime

    for raw in candidates:
        text = _clean(raw)
        if not text:
            continue
        match = re.search(r"(20\d{2}|19\d{2})", text)
        if match:
            return int(match.group(1))
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text[:10], fmt).year
            except ValueError:
                continue
    return None


def _julian_day_from_date(*candidates: Any) -> int | None:
    """Convertit une date JJ/MM/AAAA ou ISO en jour julien (contrat API dateRevenu)."""
    from datetime import date, datetime

    for raw in candidates:
        text = _clean(raw)
        if not text:
            continue
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text[:10], fmt).date()
                return parsed.toordinal() + 1721425
            except ValueError:
                continue
    return None


def resolve_tiers(identite: dict[str, Any] | None) -> str | None:
    data = identite or {}
    tiers = _clean(data.get("tiers"))
    if tiers:
        return tiers
    lookup = data.get("client_lookup") or {}
    primary = lookup.get("primary") if isinstance(lookup, dict) else None
    if isinstance(primary, dict):
        return _clean(primary.get("tiers"))
    matches = data.get("matched_clients") or lookup.get("matches") or []
    if isinstance(matches, list) and matches:
        first = matches[0]
        if isinstance(first, dict):
            return _clean(first.get("tiers"))
    return None


def build_bilan_payload_from_values(
    *,
    tiers: str,
    values: dict[str, Any],
    annee: int,
    date_revenu: int | None = None,
    flag_wlist: str = "O",
    code_statut: str = "EXPL",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "noRcTiers": str(tiers).strip(),
        "annee": int(annee),
        "flagWlist": (flag_wlist or "O").strip().upper()[:1] or "O",
        "codeStatut": (code_statut or "EXPL").strip() or "EXPL",
    }
    if date_revenu is not None:
        payload["dateRevenu"] = int(date_revenu)
    for api_key, rcc_code in _BILAN_FIELD_MAP.items():
        # CA export : si absent, on n'envoie pas le CA total sous ce nom.
        payload[api_key] = round(_num(values.get(rcc_code)), 3)
    return payload


def _ia_headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.ia_clients_api_key:
        headers["X-API-Key"] = settings.ia_clients_api_key
        headers["Authorization"] = f"Bearer {settings.ia_clients_api_key}"
    return headers


def _ia_base_url() -> str:
    base = (settings.ia_clients_base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("IA_CLIENTS_BASE_URL non configurée.")
    return base


def post_bilan(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /ia-clients/bilans — un enregistrement."""
    if not settings.ia_clients_enabled:
        raise RuntimeError("Envoi bilans désactivé (IA_CLIENTS_ENABLED=false).")
    url = f"{_ia_base_url()}/ia-clients/bilans"
    with httpx.Client(timeout=settings.ia_clients_timeout_seconds) as client:
        response = client.post(url, json=payload, headers=_ia_headers())
        body: Any
        try:
            body = response.json()
        except Exception:
            body = {"raw": (response.text or "")[:500]}
        if response.status_code >= 400:
            detail = body.get("detail") if isinstance(body, dict) else None
            raise RuntimeError(
                detail or f"API bilans HTTP {response.status_code}: {str(body)[:300]}"
            )
        return body if isinstance(body, dict) else {"data": body, "status_code": response.status_code}


def post_bilans_batch(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """POST /ia-clients/bilans/batch — plusieurs enregistrements."""
    if not settings.ia_clients_enabled:
        raise RuntimeError("Envoi bilans désactivé (IA_CLIENTS_ENABLED=false).")
    if not payloads:
        raise ValueError("Aucun bilan à envoyer.")
    url = f"{_ia_base_url()}/ia-clients/bilans/batch"
    with httpx.Client(timeout=max(30.0, settings.ia_clients_timeout_seconds * 2)) as client:
        response = client.post(url, json=payloads, headers=_ia_headers())
        try:
            body = response.json()
        except Exception:
            body = {"raw": (response.text or "")[:500]}
        if response.status_code >= 400:
            detail = body.get("detail") if isinstance(body, dict) else None
            raise RuntimeError(
                detail or f"API bilans/batch HTTP {response.status_code}: {str(body)[:300]}"
            )
        return body if isinstance(body, dict) else {"data": body, "status_code": response.status_code}


def build_bilan_from_dossier(dossier: Any) -> dict[str, Any]:
    """Construit le payload bilans depuis un RccDossier (tiers = n° tiers API search)."""
    from app.services.rcc_dossier_store import effective_values

    identite = getattr(dossier, "identite", None) or {}
    tiers = resolve_tiers(identite)
    if not tiers:
        raise ValueError(
            "N° tiers manquant : relancez l'extraction pour rapprocher le client "
            "via /ia-clients/search avant l'envoi du bilan."
        )
    values = effective_values(dossier)
    # Si le résultat n'a que current.observed_value (pas value), tenter la lecture.
    if not any(values.get(code) is not None for code in _BILAN_FIELD_MAP.values()):
        for item in (getattr(dossier, "result", None) or {}).get("fields", []) or []:
            code = item.get("code")
            if not code:
                continue
            if item.get("value") is not None:
                values[code] = item.get("value")
                continue
            current = item.get("current") or {}
            if isinstance(current, dict) and current.get("observed_value") is not None:
                values[code] = current.get("observed_value")

    annee = _parse_year(
        identite.get("period_end"),
        getattr(dossier, "exercice_date", None),
        identite.get("period_start"),
        identite.get("declaration_date"),
    )
    if annee is None:
        from datetime import datetime

        annee = datetime.utcnow().year

    date_revenu = _julian_day_from_date(
        identite.get("period_end"),
        getattr(dossier, "exercice_date", None),
        identite.get("declaration_date"),
    )
    return build_bilan_payload_from_values(
        tiers=tiers,
        values=values,
        annee=annee,
        date_revenu=date_revenu,
    )
