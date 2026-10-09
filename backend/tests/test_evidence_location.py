"""Position des valeurs dans la liasse (bouton « Voir ») : preuve V6 → position relative sur la page."""
from __future__ import annotations

import math

import pytest

from app.services.v6_result_mapper import (
    SCAN_COORDINATES,
    _evidence_for,
    locate_evidence,
    map_fields,
    relative_bbox,
)

PAGE = {"page": 4, "ocr_image_size": [1000, 2000], "rotation_clockwise": 0, "deskew_counterclockwise": 0}


def _forward(x: float, y: float, page_w: float, page_h: float, rotation: int, angle_deg: float):
    """Transformation du moteur (page rendue → image OCR), pour vérifier l'inverse."""
    if rotation == 90:
        x, y = page_h - y, x
    elif rotation == 180:
        x, y = page_w - x, page_h - y
    elif rotation == 270:
        x, y = y, page_w - x
    width, height = (page_h, page_w) if rotation in (90, 270) else (page_w, page_h)
    a = math.radians(angle_deg)
    cx, cy = width / 2, height / 2
    dx, dy = x - cx, y - cy
    return math.cos(a) * dx + math.sin(a) * dy + cx, -math.sin(a) * dx + math.cos(a) * dy + cy, width, height


def test_straight_scan_is_a_simple_ratio():
    box = relative_bbox([100, 400, 300, 440], SCAN_COORDINATES, PAGE)
    assert box == [0.1, 0.2, 0.3, 0.22]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("angle", [0.0, 1.5, -2.0])
def test_rotation_and_deskew_are_undone(rotation, angle):
    page_w, page_h = 1240, 1754  # page A4 rendue à 150 dpi
    target = (0.62, 0.41)  # point de la page, en proportion
    x, y, width, height = _forward(target[0] * page_w, target[1] * page_h, page_w, page_h, rotation, angle)
    page = {"ocr_image_size": [width, height], "rotation_clockwise": rotation, "deskew_counterclockwise": angle}
    box = relative_bbox([x - 1, y - 1, x + 1, y + 1], SCAN_COORDINATES, page)
    centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    assert centre[0] == pytest.approx(target[0], abs=0.002)
    assert centre[1] == pytest.approx(target[1], abs=0.002)


def test_native_pdf_points_are_left_to_the_viewer():
    # PDF natif : coordonnées en points, converties par le lecteur pdf.js.
    assert relative_bbox([50, 60, 120, 70], "pdf_points_unrotated", PAGE) is None


def test_missing_page_record_or_bbox_gives_no_position():
    assert relative_bbox([1, 2, 3, 4], SCAN_COORDINATES, None) is None
    assert relative_bbox(None, SCAN_COORDINATES, PAGE) is None
    assert relative_bbox([1, 2, 3, 4], SCAN_COORDINATES, {"page": 4}) is None


def test_evidence_keeps_engine_geometry():
    entry = {
        "label": "Chiffre d'affaires",
        "current": 1200000,
        "evidence": {"current": {
            "page": 4, "raw": "1 200 000", "label": "Chiffre d'affaires",
            "bbox": [100, 400, 300, 440], "coordinate_space": SCAN_COORDINATES,
        }},
    }
    evidence = _evidence_for(entry, "current")[0]
    assert evidence.bbox == [100.0, 400.0, 300.0, 440.0]
    assert evidence.coordinate_space == SCAN_COORDINATES


def test_locate_evidence_fills_relative_box_for_scanned_pages():
    canonical = {
        "resultat_net": {
            "label": "Résultat net",
            "current": 85000,
            "evidence": {"current": {
                "page": 4, "raw": "85 000", "bbox": [100, 400, 300, 440],
                "coordinate_space": SCAN_COORDINATES,
            }},
        }
    }
    fields = map_fields(canonical)
    locate_evidence(fields, [PAGE])
    rn = next(field for field in fields if field.code == "RESULTAT_NET")
    assert rn.current.evidence[0].bbox_relative == [0.1, 0.2, 0.3, 0.22]
