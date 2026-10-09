"""N° tiers du référentiel clients : retenu automatiquement, choisi ou saisi, puis envoyé à Ekip."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.services.ia_clients_service import build_bilan_from_dossier, resolve_tiers
from app.services.rcc_dossier_store import RccDossier, export_dossier_clean, rcc_dossier_store

client = TestClient(app)

TEST_USER = {"id": "t", "username": "test.rcc1", "display_name": "Test RCC1", "roles": ["RCC_USER"]}

CANDIDATES = [
    {"tiers": "096569", "raison_sociale": "SAR KAMANE TRANS", "ice": "000024978000035"},
    {"tiers": "022654", "raison_sociale": "STE EUROMEDIA", "ice": "001531725000054"},
]


@pytest.fixture(autouse=True)
def _authenticated():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _lookup(status: str, matches: list[dict] | None = None) -> dict:
    matches = matches or []
    return {
        "status": status,
        "query": {"ice": "001531725000054"},
        "matches": matches,
        "primary": matches[0] if matches else None,
    }


@pytest.fixture
def make_dossier():
    created: list[str] = []

    def _make(dossier_id: str, identite: dict) -> RccDossier:
        dossier = RccDossier(
            id=dossier_id, job_id=None, client_name="STE EUROMEDIA", ice="001531725000054",
            credit_amount=None, exercice_date="31/12/2025", status="pending",
            created_at="2026-10-08T00:00:00+00:00", updated_at="2026-10-08T00:00:00+00:00",
            sector=None, filename=None, pdf_path=None, completeness_pct=0,
            result={"fields": []}, scoring_result=None,
            identite={"period_end": "31/12/2025", **identite},
        )
        rcc_dossier_store.put(dossier)
        created.append(dossier_id)
        return dossier

    yield _make
    for dossier_id in created:
        rcc_dossier_store.delete(dossier_id)


def _put_tiers(dossier_id: str, tiers: str, source: str):
    return client.put(f"/api/v1/rcc/dossiers/{dossier_id}/tiers", json={"tiers": tiers, "source": source})


# --- Règle de choix du n° tiers -------------------------------------------------------------

def test_single_match_tiers_is_kept():
    identite = {"tiers": "022654", "client_lookup": _lookup("MATCHED", CANDIDATES[1:])}
    assert resolve_tiers(identite) == "022654"


def test_multiple_matches_need_a_choice():
    # Plus de choix automatique de la première ligne : risque d'envoyer au mauvais client.
    identite = {"tiers": "096569", "client_lookup": _lookup("MULTIPLE", CANDIDATES)}
    assert resolve_tiers(identite) is None
    chosen = {**identite, "tiers": "022654", "tiers_source": "selected"}
    assert resolve_tiers(chosen) == "022654"


def test_no_match_uses_manual_tiers():
    identite = {"client_lookup": _lookup("NOT_FOUND")}
    assert resolve_tiers(identite) is None
    assert resolve_tiers({**identite, "tiers": "T-77", "tiers_source": "manual"}) == "T-77"


# --- Route PUT /rcc/dossiers/{id}/tiers ----------------------------------------------------

def test_manual_tiers_when_no_client(make_dossier):
    make_dossier("RCC-TIERS-NONE", {"client_lookup": _lookup("NOT_FOUND")})
    response = _put_tiers("RCC-TIERS-NONE", "  T-9981 ", "manual")
    assert response.status_code == 200
    body = response.json()["dossier"]
    assert body["tiers"] == "T-9981"
    assert body["identite"]["tiers"] == "T-9981"
    assert body["tiers_source"] == "manual"

    audit = client.get("/api/v1/rcc/dossiers/RCC-TIERS-NONE/audit").json()["items"]
    assert any(item["action"] == "N° tiers saisi" and item["after"] == "T-9981" for item in audit)


def test_manual_tiers_when_api_down(make_dossier):
    make_dossier("RCC-TIERS-ERR", {"client_lookup": _lookup("ERROR")})
    assert _put_tiers("RCC-TIERS-ERR", "T-1", "manual").status_code == 200


def test_select_one_of_multiple_clients(make_dossier):
    make_dossier("RCC-TIERS-MULTI", {"client_lookup": _lookup("MULTIPLE", CANDIDATES)})
    assert _put_tiers("RCC-TIERS-MULTI", "999999", "selected").status_code == 422
    response = _put_tiers("RCC-TIERS-MULTI", "022654", "selected")
    assert response.status_code == 200
    assert response.json()["dossier"]["tiers"] == "022654"


def test_single_match_tiers_is_definitive(make_dossier):
    make_dossier("RCC-TIERS-ONE", {"tiers": "022654", "client_lookup": _lookup("MATCHED", CANDIDATES[1:])})
    assert _put_tiers("RCC-TIERS-ONE", "T-2", "manual").status_code == 409


def test_blank_tiers_is_rejected(make_dossier):
    make_dossier("RCC-TIERS-BLANK", {"client_lookup": _lookup("NOT_FOUND")})
    assert _put_tiers("RCC-TIERS-BLANK", "   ", "manual").status_code == 422


# --- Le n° tiers retenu part dans le JSON et vers Ekip -------------------------------------

def test_tiers_goes_to_json_and_ekip(make_dossier):
    dossier = make_dossier("RCC-TIERS-EKIP", {"client_lookup": _lookup("MULTIPLE", CANDIDATES)})
    with pytest.raises(ValueError, match="choisissez le client"):
        build_bilan_from_dossier(dossier)

    _put_tiers("RCC-TIERS-EKIP", "022654", "selected")
    stored = rcc_dossier_store.get("RCC-TIERS-EKIP")
    assert export_dossier_clean(stored)["tiers"] == "022654"
    assert build_bilan_from_dossier(stored)["noRcTiers"] == "022654"


def test_scoring_reimport_keeps_analyst_tiers(make_dossier, monkeypatch):
    # Un dossier du scoring est réimporté à chaque lecture : le tiers saisi ne doit pas être perdu.
    from types import SimpleNamespace

    from app.services.rcc_from_scoring import _fill_dossier

    monkeypatch.setattr("app.services.rcc_from_scoring._sector_candidates", lambda _record: (None,))

    dossier = make_dossier(
        "RCC-TIERS-REIMPORT",
        {"tiers": "T-55", "tiers_source": "manual", "client_lookup": _lookup("NOT_FOUND")},
    )
    fresh_identite = {"raison_sociale": "STE EUROMEDIA", "client_lookup": _lookup("NOT_FOUND")}
    result = SimpleNamespace(completeness_pct=0)
    record = SimpleNamespace(name="STE EUROMEDIA", ice=None, sector=None, nature=None)
    _fill_dossier(dossier, record=record, result=result, projected={}, identite=fresh_identite)
    assert dossier.identite["tiers"] == "T-55"
    assert resolve_tiers(dossier.identite) == "T-55"


# --- Relance de la recherche : POST /rcc/dossiers/{id}/client-lookup/refresh ----------------

def _fake_search(monkeypatch, status: str, matches: list[dict] | None = None, calls: list | None = None):
    from app.schemas.analyse import ClientLookup, IaClientMatch

    items = [IaClientMatch(**item) for item in (matches or [])]

    def search(**query):
        if calls is not None:
            calls.append(query)
        return ClientLookup(status=status, query={"ice": "001531725000054"}, matches=items,
                            primary=items[0] if items else None, message=f"recherche {status}")

    monkeypatch.setattr("app.services.ia_clients_service.search_ia_clients", search)


def _refresh(dossier_id: str):
    return client.post(f"/api/v1/rcc/dossiers/{dossier_id}/client-lookup/refresh")


def test_refresh_after_api_down_finds_the_client(make_dossier, monkeypatch):
    calls: list = []
    make_dossier("RCC-REFRESH-OK", {"client_lookup": {**_lookup("ERROR"), "query": {"ice": "001531725000054", "identifiantFiscal": "1103297"}}})
    _fake_search(monkeypatch, "MATCHED", CANDIDATES[1:], calls)
    response = _refresh("RCC-REFRESH-OK")
    assert response.status_code == 200
    body = response.json()["dossier"]
    assert body["tiers"] == "022654"
    assert body["client_lookup"]["status"] == "MATCHED"
    # La recherche reprend les identifiants de la recherche initiale.
    assert calls == [{"ice": "001531725000054", "rc": None, "identifiant_fiscal": "1103297"}]
    audit = client.get("/api/v1/rcc/dossiers/RCC-REFRESH-OK/audit").json()["items"]
    assert any(item["action"] == "Référentiel clients relancé (MATCHED)" for item in audit)


def test_refresh_still_down_keeps_manual_tiers(make_dossier, monkeypatch):
    make_dossier("RCC-REFRESH-DOWN", {"tiers": "T-9", "tiers_source": "manual", "client_lookup": _lookup("ERROR")})
    _fake_search(monkeypatch, "ERROR")
    assert _refresh("RCC-REFRESH-DOWN").json()["dossier"]["tiers"] == "T-9"


def test_refresh_single_match_replaces_manual_tiers(make_dossier, monkeypatch):
    make_dossier("RCC-REFRESH-REPLACE", {"tiers": "T-9", "tiers_source": "manual", "client_lookup": _lookup("NOT_FOUND")})
    _fake_search(monkeypatch, "MATCHED", CANDIDATES[1:])
    body = _refresh("RCC-REFRESH-REPLACE").json()["dossier"]
    assert body["tiers"] == "022654"
    assert body["tiers_source"] is None


def test_refresh_multiple_keeps_a_still_valid_choice(make_dossier, monkeypatch):
    make_dossier("RCC-REFRESH-MULTI", {"tiers": "022654", "tiers_source": "selected", "client_lookup": _lookup("MULTIPLE", CANDIDATES)})
    _fake_search(monkeypatch, "MULTIPLE", CANDIDATES)
    assert _refresh("RCC-REFRESH-MULTI").json()["dossier"]["tiers"] == "022654"
    _fake_search(monkeypatch, "MULTIPLE", CANDIDATES[:1])
    assert _refresh("RCC-REFRESH-MULTI").json()["dossier"]["tiers"] is None


def test_scoring_reimport_keeps_refreshed_lookup(make_dossier, monkeypatch):
    from types import SimpleNamespace

    from app.schemas.analyse import ClientLookup, IaClientMatch
    from app.services.ia_clients_service import apply_client_lookup
    from app.services.rcc_from_scoring import _fill_dossier

    monkeypatch.setattr("app.services.rcc_from_scoring._sector_candidates", lambda _record: (None,))
    match = IaClientMatch(**CANDIDATES[1])
    dossier = make_dossier("RCC-REFRESH-REIMPORT", {"client_lookup": _lookup("ERROR")})
    dossier.identite = apply_client_lookup(dossier.identite, ClientLookup(status="MATCHED", matches=[match], primary=match))
    stale = {"raison_sociale": "STE EUROMEDIA", "client_lookup": _lookup("ERROR")}
    _fill_dossier(dossier, record=SimpleNamespace(name="STE EUROMEDIA", ice=None), result=SimpleNamespace(completeness_pct=0), projected={}, identite=stale)
    assert dossier.identite["client_lookup"]["status"] == "MATCHED"
    assert resolve_tiers(dossier.identite) == "022654"


def test_missing_tiers_message_points_to_referential(make_dossier):
    dossier = make_dossier("RCC-TIERS-MISSING", {"client_lookup": _lookup("NOT_FOUND")})
    with pytest.raises(ValueError, match="saisissez-le dans le Référentiel clients"):
        build_bilan_from_dossier(dossier)
