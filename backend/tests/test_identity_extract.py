from app.services.identity_extract import _extract_rc, _merge_identity
from app.services.v6_result_mapper import identity_from_v6


def test_extract_rc_from_bilan_header():
    text = """
    Raison Sociale : TRANSPORT ATLAS SARL
    ICE : 002345678901234
    Identifiant fiscal : 52601461
    RC : 123456/CASABLANCA
    """
    assert _extract_rc(text) == "123456/CASABLANCA"


def test_identity_from_v6_fills_ice_and_if():
    identity = identity_from_v6(
        {
            "ice": "003120883000059",
            "identifiant_fiscal": "52601461",
            "raison_sociale": "DMT ADVISORY",
        }
    )
    assert identity.ice == "003120883000059"
    assert identity.identifiant_fiscal == "52601461"


def test_resolve_tesseract_cmd_finds_windows_binary():
    from app.services.v6_extractor_bridge import resolve_tesseract_cmd

    cmd = resolve_tesseract_cmd()
    assert cmd.lower().endswith("tesseract.exe") or cmd.lower().endswith("tesseract")
    from pathlib import Path

    assert Path(cmd).is_file()


def test_merge_identity_keeps_first_non_empty():
    base = {"ice": "111", "rc": None}
    merged = _merge_identity(base, {"ice": "222", "raison_sociale": "ATLAS"})
    assert merged["ice"] == "111"
    assert merged["raison_sociale"] == "ATLAS"
