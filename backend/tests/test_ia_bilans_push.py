from app.services.ia_clients_service import (
    build_bilan_payload_from_values,
    build_search_query,
    resolve_tiers,
)


def test_resolve_tiers_from_identite():
    assert resolve_tiers({"tiers": "096569"}) == "096569"
    assert resolve_tiers({"client_lookup": {"primary": {"tiers": "096569"}}}) == "096569"
    assert resolve_tiers({}) is None


def test_build_bilan_payload_maps_rcc_fields():
    payload = build_bilan_payload_from_values(
        tiers="096569",
        annee=2025,
        date_revenu=2461041,
        values={
            "FONDS_PROPRES": 1500000,
            "ACTIFS_IMMOBILISES": 900000,
            "CA_EXPORT": 250000,
            "DETTES_BANCAIRES_MLT": 400000,
            "DETTES_BANCAIRES_CT": 120000,
            "PASSIF_CIRCULANT": 300000,
            "DETTES_FOURNISSEURS": 180000,
            "COMPTE_COURANT_ASSOCIES": 50000,
            "TRESORERIE_PASSIF": 20000,
            "ACTIF_CIRCULANT": 700000,
            "CREANCES_CLIENTS": 350000,
            "TRESORERIE_ACTIF": 80000,
            "CAISSE": 5000,
            "ACHATS_REVENDUS": 600000,
            "ACHATS_CONSOMMES": 450000,
            "AUTRES_CHARGES_EXTERNES": 120000,
            "CHARGES_INTERETS": 35000,
            "RESULTAT_NET": 210000,
        },
    )
    assert payload["noRcTiers"] == "096569"
    assert payload["annee"] == 2025
    assert payload["capitauxPermanents"] == 1500000.0
    assert payload["actifsImmobilises"] == 900000.0
    assert payload["resultatNet"] == 210000.0
    assert payload["codeStatut"] == "EXPL"
    assert build_search_query(ice="1")["ice"] == "000000000000001"
