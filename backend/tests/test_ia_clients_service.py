from app.services.ia_clients_service import build_search_query, search_ia_clients


def test_build_search_query_uses_available_fields_only():
    assert build_search_query(ice="24978000035") == {"ice": "000024978000035"}
    assert build_search_query(rc="252633/Casablanca") == {"rc": "252633"}
    assert build_search_query(
        ice="000024978000035",
        rc="252633",
        identifiant_fiscal="40463055",
    ) == {
        "ice": "000024978000035",
        "rc": "252633",
        "identifiantFiscal": "40463055",
    }
    assert build_search_query() == {}


def test_search_ia_clients_matched(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "ice": "000024978000035",
                    "tiers": "096569",
                    "rc": "252633",
                    "identifiantFiscal": "40463055",
                    "raisonSociale": "SAR KAMANE TRANS",
                }
            ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None, headers=None):
            assert "/ia-clients/search" in url
            assert params["ice"] == "000024978000035"
            return FakeResponse()

    monkeypatch.setattr("app.services.ia_clients_service.httpx.Client", FakeClient)
    result = search_ia_clients(ice="000024978000035")
    assert result.status == "MATCHED"
    assert result.primary is not None
    assert result.primary.tiers == "096569"
    assert result.primary.raison_sociale == "SAR KAMANE TRANS"


def test_search_ia_clients_skipped_without_identifiers():
    result = search_ia_clients()
    assert result.status == "SKIPPED"
