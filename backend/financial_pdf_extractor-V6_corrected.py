from __future__ import annotations

"""Local extractor for Moroccan financial statements, version 3.

Python 3.11+. PyMuPDF for native cells; Tesseract + OpenCV for scanned cells.
Amounts remain Decimal strings, with per-cell provenance and explicit states.
Optional, budgeted Ollama cell verification; no automatic imputation of blanks.
See README.md for installation, CLI, output contract, and validation limits.
"""

import argparse
import contextlib
import bisect
import csv
import dataclasses
import hashlib
import io
import json
import logging
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz

VERSION = "5.0.0"
CACHE_VERSION = "v5.0-cells-1"
LOG = logging.getLogger("financial_extractor")
VALUE_NAMES = ("current", "previous", "brut_current", "amort_prov_current",
               "operations_current", "operations_prior_period")
FINANCIAL_SECTIONS = {"bilan_actif", "bilan_passif", "cpc", "esg", "detail_cpc"}


@dataclass
class FinancialRow:
    page: int
    section: str
    group_label: str
    label: str
    current: str | None = None
    previous: str | None = None
    brut_current: str | None = None
    amort_prov_current: str | None = None
    operations_current: str | None = None
    operations_prior_period: str | None = None
    canonical_key: str | None = None
    mapping_method: str | None = None
    match_score: float | None = None
    source_parser: str = ""
    confidence: float = 0.0  # heuristic quality indicator, NOT a probability
    raw: str = ""
    table_id: int = 0
    row_index: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    dpi: int = 350
    ocr_language: str = "fra+eng"
    tesseract_cmd: str = "tesseract"
    ocr_timeout: int = 60
    ocr: str = "auto"
    rotation: int | None = None  # clockwise degrees added to displayed page
    min_ocr_confidence: float = 60.0
    cache: bool = True
    ollama_url: str | None = None
    max_llm_calls: int = 4
    llm_timeout: int = 30
    semantic_fallback: bool = False
    scan_backend: str = 'tesseract'
    liteparse_cmd: str | None = None
    backend_timeout: int = 180


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
        json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
    temp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def semantic_label(value: str) -> str:
    value = re.sub(r'^[\s*=»«•▪■]+', '', value)
    value = re.sub(r'^[amns]\s+(?=[A-ZÉÈ])', '', value)
    value = re.sub(r"\(\s*\d+\s*\)", " ", value)
    n = normalize_label(value)
    n = re.sub(r"^\d+\s+", "", n)
    if not n.startswith("total "):
        n = re.sub(r"^[ivxlcdm]+\s+", "", n)
    return n.strip()


def parse_amount(raw: str | None, *, ocr: bool = False) -> dict[str, Any]:
    """Parse an entire numeric cell, never the first number in arbitrary text.

    One or two decimal places; 3-digit separators denote thousands. A blank
    or dash is not zero. Parentheses and trailing minus signs are supported.
    Only isolated O/o in otherwise numeric OCR cells may be repaired.
    """
    original = raw or ""
    text = unicodedata.normalize("NFKC", original).strip()
    out = {"raw": original, "value": None, "status": "blank", "repairs": []}
    if not text:
        return out
    if text in {"-", "—", "–", "−", "_"}:
        out["status"] = "dash"
        return out
    text = text.replace("—", "-").replace("−", "-").replace("–", "-").replace("’", "'")
    text = re.sub(r"\s+(?:DH|DHS|MAD)$", "", text, flags=re.I)
    if ocr and re.fullmatch(r"[\dOo\s.,'()+\-]+", text) and re.search(r"[Oo]", text):
        # Do not turn an ordinary word into a number.
        if re.search(r"\d", text):
            text = text.translate(str.maketrans({"O": "0", "o": "0"}))
            out["repairs"].append("OCR_O_to_0")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    if text.endswith("-"):
        if negative:
            out["status"] = "unparsed"
            return out
        negative, text = True, text[:-1].strip()
    if not re.search(r'[.,]',text) and re.search(r'\d\s+\d',text):
        groups = re.sub(r'^[+-]','',text).split()
        if not (1<=len(groups[0])<=3 and all(len(g)==3 for g in groups[1:])):
            out['status'] = 'unparsed'
            return out
    text = re.sub(r"\s", "", text).replace("'", "")
    if not re.fullmatch(r"[+-]?\d[\d.,]*", text):
        out["status"] = "unparsed"
        return out
    if negative and text[0] in "+-":
        out["status"] = "unparsed"
        return out
    sign = "-" if negative else ""
    if text.startswith(("+", "-")):
        sign, text = ("-" if text[0] == "-" else ""), text[1:]
    last = max(text.rfind(","), text.rfind("."))
    if last >= 0 and len(text) - last - 1 in (1, 2):
        integer, fraction = text[:last], text[last + 1:]
        # Other punctuation must have valid grouping. Spaces were removed
        # because OCR often splits a group; multiple amounts still fail here.
        if "," in integer or "." in integer:
            parts = re.split(r"[.,]", integer)
            if not (1 <= len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:])):
                out["status"] = "unparsed"
                return out
        text = re.sub(r"[.,]", "", integer) + "." + fraction
    elif last >= 0:
        parts = re.split(r"[.,]", text)
        if not (1 <= len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:])):
            out["status"] = "unparsed"
            return out
        text = "".join(parts)
    try:
        amount = Decimal(sign + text)
        out.update(value=format(amount, "f"), status="explicit_zero" if amount == 0 else "observed")
    except InvalidOperation:
        out["status"] = "unparsed"
    return out



def parse_amount_ocr_relaxed(raw: str | None) -> dict[str, Any]:
    """OCR-only numeric parsing with *very* limited punctuation cleanup.

    This never guesses missing digits.  It only removes harmless leading/trailing
    punctuation (e.g. ':' or '|') around an otherwise numeric cell.  Ambiguous
    glyphs such as '$', letters, or embedded words remain unparsed so that a
    zero-confidence local retry cannot silently replace a better OCR observation.
    """
    first = parse_amount(raw, ocr=True)
    if first["value"] is not None or first["status"] in {"blank", "dash"}:
        return first
    original = raw or ""
    text = unicodedata.normalize("NFKC", original).strip()
    # A trailing exclamation mark in a two-decimal OCR cell is a frequent glyph
    # confusion for digit 1.  Restrict the repair to the fractional part only.
    frac_repaired=text
    if re.search(r'[,.]\d!$',frac_repaired):
        frac_repaired=frac_repaired[:-1]+'1'
    elif re.search(r'[,.]!\d$',frac_repaired):
        pos=max(frac_repaired.rfind(','),frac_repaired.rfind('.'))+1
        frac_repaired=frac_repaired[:pos]+'1'+frac_repaired[pos+1:]
    # Only punctuation that cannot encode a digit is removed.  '$' is excluded
    # intentionally because OCR often uses it for 1/5 and guessing would be unsafe.
    cleaned = re.sub(r"^[\s:;|\[\]{}<>]+", "", frac_repaired)
    cleaned = re.sub(r"[\s:;|\[\]{}<>]+$", "", cleaned)
    if cleaned == text or not re.search(r"\d", cleaned):
        return first
    second = parse_amount(cleaned, ocr=True)
    if second["value"] is not None:
        second["raw"] = original
        if frac_repaired != text:
            second.setdefault("repairs", []).append("OCR_fraction_exclamation_to_1")
        if cleaned != frac_repaired:
            second.setdefault("repairs", []).append("OCR_trim_outer_punctuation")
        second["normalized_numeric_text"] = cleaned
        return second
    return first


def extract_amount_tokens(text: str | None, *, max_tokens: int = 4) -> list[dict[str, Any]]:
    """Extract amount tokens from a structurally known numeric OCR cell.

    Decimal amounts are preferred because they give an unambiguous boundary
    between two merged DGI period columns.  This function is never used on free
    prose, only on cells already identified as amount columns.
    """
    src = unicodedata.normalize("NFKC", text or "")
    out=[]
    # Non-greedy body stops at the first decimal separator followed by 2 digits;
    # this correctly splits e.g. "4871 971,19 17 552 588,99".
    decimal_pat=re.compile(r"(?<![A-Za-z0-9])[-+−–—]?\s*\d[\d .']*?[,.]\d{2}(?!\d)")
    for m in decimal_pat.finditer(src):
        raw=m.group(0).strip()
        parsed=parse_amount_ocr_relaxed(raw)
        if parsed['value'] is not None:
            out.append({'raw':raw,'value':parsed['value'],'span':m.span(),'repairs':parsed.get('repairs',[])})
            if len(out)>=max_tokens:return out
    if out:
        return out
    # Integer fallback, intentionally stricter and only useful when no decimal
    # amounts were present at all.
    int_pat=re.compile(r"(?<![A-Za-z0-9])[-+]?\s*(?:\d{1,3}(?:[ .']\d{3})+|\d+)(?![A-Za-z0-9,.])")
    for m in int_pat.finditer(src):
        raw=m.group(0).strip(); parsed=parse_amount_ocr_relaxed(raw)
        if parsed['value'] is not None:
            out.append({'raw':raw,'value':parsed['value'],'span':m.span(),'repairs':parsed.get('repairs',[])})
            if len(out)>=max_tokens:break
    return out

def normalize_amount(raw: str | None) -> str | None:
    return parse_amount(raw)["value"]


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def dec_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def detect_section(text: str) -> str:
    """Titles first, then a conjunction of section-specific column/row cues."""
    n = normalize_label(text)
    for title,section in {
        'tableau des amortissements':'annexe_amortissements',
        'tableau des provisions':'annexe_provisions',
        'tableau des biens en credit bail':'annexe_credit_bail',
        'tableau des plus ou moins values':'annexe_cessions',
        'tableau des titres de participation':'annexe_participations',
        'tableau des immobilisations':'annexe_immobilisations',
        'tableau de financement':'annexe_financement',
    }.items():
        if title in n:
            return section
    if "repartition du capital" in n:
        return "capital_repartition"
    if "resultat net fiscal" in n and ("passage" in n or "reintegrations" in n):
        return "resultat_fiscal"
    if "detail des postes" in n:
        return "detail_cpc"
    if "soldes de gestion" in n or "tableau de formation des resultats" in n:
        return "esg"
    if 'capacite d autofinancement' in n or ('autofinancement' in n and 'valeur ajoutee' in n):
        return 'esg'
    if re.search(r"(?:compte (?:de |des )?)?produits et charges", n):
        return "cpc"
    if re.search(r"bilan\s+(?:du\s+)?passif", n):
        return "bilan_passif"
    if re.search(r"bilan\s+(?:de l\s+)?actif", n):
        return "bilan_actif"
    if "operations propres" in n and ("totaux" in n or "concernant" in n):
        return "cpc"
    if ("brut" in n and "net" in n and ("amort" in n or "provisions" in n)):
        return "bilan_actif"
    if "capitaux propres" in n and ("financement" in n or "reserve legale" in n):
        return "bilan_passif"
    if 'immobilisations' in n and 'actif' in n and ('net' in n or 'brut' in n):
        return 'bilan_actif'
    if ('resultat financier' in n and ('charges' in n or 'produits' in n)) or ('resultat net' in n and 'total' in n and 'operations' in n):
        return 'cpc'
    return "generic"

@dataclass
class Identity:
    identifiant_fiscal: str | None = None
    ice: str | None = None
    raison_sociale: str | None = None
    taxe_professionnelle: str | None = None
    ville: str | None = None
    adresse: str | None = None
    activite: str | None = None
    secteur: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    declaration_date: str | None = None
    declaration_time: str | None = None
    reference: str | None = None
    evidence: dict[str, str] = field(default_factory=dict)

def strip_accents(value: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(ch)
    )

def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()

def normalize_label(value: str) -> str:
    value = strip_accents(value or "").lower()
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = value.replace("(", " ").replace(")", " ")
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _clean_identity_value(value: str | None) -> str | None:
    if value is None:
        return None
    v = compact_text(value).strip(" |:-")
    return v or None

def extract_identity_from_text(text: str) -> Identity:
    identity = Identity()
    src = text.replace("\u00A0", " ")

    # Exact period. Never infer it from year.
    period = re.search(
        r"p[ée]riode\s+du\s+(\d{2}/\d{2}/\d{4})\s+au\s+(\d{2}/\d{2}/\d{4})",
        src,
        re.I | re.S,
    )
    if period:
        identity.period_start = period.group(1)
        identity.period_end = period.group(2)
        identity.evidence["period"] = compact_text(period.group(0))

    declaration = re.search(
        r"(?:d[ée]claration\s+souscrite|souscrite)\s+le\s+"
        r"(\d{2}/\d{2}/\d{4})(?:\s+(\d{2}:\d{2}:\d{2}))?",
        src,
        re.I | re.S,
    )
    if declaration:
        identity.declaration_date = declaration.group(1)
        identity.declaration_time = declaration.group(2)

    ref = re.search(
        r"(?:sous\s+r[ée]f[ée]rence|r[ée]f[ée]rence)\s*[: ]\s*([A-Za-z0-9_\-]+)",
        src,
        re.I,
    )
    if ref:
        identity.reference = ref.group(1).rstrip(")")

    id_patterns = {
        "identifiant_fiscal": r"Identifiant\s+fiscal\s*[:\-]?\s*([0-9]{5,20})",
        "ice": r"\bICE\s*[:\-]?\s*([0-9]{10,20})",
        "taxe_professionnelle": (
            r"(?:Art\.?\s*)?Taxe\s+professionnelle\s*[:\-]?\s*([0-9]{4,20})"
        ),
    }
    for name, pattern in id_patterns.items():
        m = re.search(pattern, src, re.I)
        if m:
            value = m.group(1)
            setattr(identity, name, value)
            identity.evidence[name] = value

    # Line-oriented fields. Works well after visual-line reconstruction.
    for line in src.splitlines():
        line = compact_text(line)

        m = re.match(r"Raison\s+Sociale\s*[:\-]?\s*(.+)$", line, re.I)
        if m and not identity.raison_sociale:
            identity.raison_sociale = _clean_identity_value(m.group(1))
            if identity.raison_sociale:
                identity.evidence["raison_sociale"] = identity.raison_sociale

        m = re.match(r"Adresse\s*[:\-]?\s*(.+)$", line, re.I)
        if m and not identity.adresse:
            identity.adresse = _clean_identity_value(m.group(1))
            if identity.adresse:
                identity.evidence["adresse"] = identity.adresse

        m = re.match(r"Ville\s*[:\-]?\s*(.+)$", line, re.I)
        if m and not identity.ville:
            identity.ville = _clean_identity_value(m.group(1))
            if identity.ville:
                identity.evidence["ville"] = identity.ville

        # Activity can share a visual line with IF on these forms.
        m = re.search(r"Activit[ée]\s*[:\-]?\s*(.+)$", line, re.I)
        if m and not identity.activite:
            identity.activite = _clean_identity_value(m.group(1))
            if identity.activite:
                identity.evidence["activite"] = identity.activite

    # Conservative fallbacks for non-line-preserving OCR.
    if not identity.raison_sociale:
        m = re.search(
            r"Raison\s+Sociale\s*[:\-]?\s*(.+?)(?=\s+(?:ICE|Art\.?\s*Taxe|Adresse|Ville|Activit[ée])\b|$)",
            compact_text(src),
            re.I,
        )
        if m:
            identity.raison_sociale = _clean_identity_value(m.group(1))

    if not identity.adresse:
        m = re.search(
            r"Adresse\s*[:\-]?\s*(.+?)(?=\s+(?:Ville|Activit[ée]|ICE|Art\.?\s*Taxe)\b|$)",
            compact_text(src),
            re.I,
        )
        if m:
            identity.adresse = _clean_identity_value(m.group(1))

    if not identity.ville:
        m = re.search(
            r"Ville\s*[:\-]?\s*([0-9A-Za-z .,'/\-]{2,50}?)(?=\s+(?:Activit[ée]|ICE|Adresse|Art\.?\s*Taxe)\b|$)",
            compact_text(src),
            re.I,
        )
        if m:
            identity.ville = _clean_identity_value(m.group(1))

    if not identity.activite:
        m = re.search(
            r"Activit[ée]\s*[:\-]?\s*(.+?)(?=\s+(?:Raison\s+Sociale|ICE|Art\.?\s*Taxe|Adresse|Ville)\b|$)",
            compact_text(src),
            re.I,
        )
        if m:
            identity.activite = _clean_identity_value(m.group(1))

    return identity

def identity_completeness(identity: Identity) -> int:
    fields = (
        "identifiant_fiscal",
        "ice",
        "raison_sociale",
        "taxe_professionnelle",
        "ville",
        "adresse",
        "activite",
        "period_start",
        "period_end",
    )
    return sum(getattr(identity, f) not in (None, "") for f in fields)

FIELD_SECTION_PRIORITY: dict[str, list[str]] = {
    # balance sheet
    "capital": ["bilan_passif", "capital_repartition"],
    "fonds_propres": ["bilan_passif"],
    "report_a_nouveau": ["bilan_passif"],
    "resultat_net": ["bilan_passif", "cpc", "esg", "resultat_fiscal"],
    "dettes_financement": ["bilan_passif"],
    "total_immobilise": ["bilan_actif"],
    "total_actif": ["bilan_actif"],
    "total_passif": ["bilan_passif"],
    "stocks": ["bilan_actif"],
    "clients": ["bilan_actif"],
    "etat_debiteur": ["bilan_actif"],
    "comptes_associes_actif": ["bilan_actif"],
    "banques_actif": ["bilan_actif"],
    "fournisseurs": ["bilan_passif"],
    "etat_crediteur": ["bilan_passif"],
    "comptes_associes_passif": ["bilan_passif"],
    "banques_passif": ["bilan_passif"],

    # income statement
    "chiffre_affaires": ["cpc", "detail_cpc", "esg"],
    "autres_charges_externes": ["cpc", "esg", "detail_cpc"],
    "dotations_exploitation": ["cpc", "esg"],
    "resultat_exploitation": ["cpc", "esg"],
    "produits_financiers": ["cpc", "detail_cpc", "esg"],
    "charges_interets": ["cpc", "detail_cpc"],
    "charges_financieres": ["cpc", "detail_cpc"],
    "resultat_financier": ["cpc", "esg"],
    "charges_non_courantes": ["cpc", "detail_cpc"],
    "resultat_non_courant": ["cpc", "esg"],
    "resultat_avant_impots": ["cpc", "esg"],
    "impots_resultats": ["cpc", "esg"],
    "caf": ["esg"],
    "redevances_credit_bail": ["detail_cpc"],
}
def _legacy_section_rules(row: FinancialRow) -> FinancialRow:
    """
    No global fuzzy matching.
    A row can only map to keys allowed for its financial section.
    """
    n = normalize_label(row.label)
    s = semantic_label(row.label)
    g = normalize_label(row.group_label)

    key: str | None = None
    method = "strict_section_rule"
    score = 100.0

    # ---------------------------- BILAN ACTIF ----------------------------
    if row.section == "bilan_actif":
        if "total general" in n:
            key = "total_actif"
        elif s == "total i" or s.startswith("total i a+b+c+d+e"):
            key = "total_immobilise"
        elif s == "total ii" or s.startswith("total ii f+g+h+i"):
            key = "total_actif_circulant"
        elif s == "total iii":
            key = "tresorerie_actif"
        elif s.startswith("immobilisations en non valeurs") or s.startswith("immobilisation en non valeur"):
            key = "immobilisations_non_valeurs"
        elif s.startswith("immobilisations incorporelles"):
            key = "immobilisations_incorporelles"
        elif s.startswith("immobilisations corporelles"):
            key = "immobilisations_corporelles"
        elif "mobilier" in s and "materiel de bureau" in s:
            key = "mobilier_materiel_bureau"
        elif s.startswith("immobilisations financieres"):
            key = "immobilisations_financieres"
        elif s == "autres creances financieres":
            key = "autres_creances_financieres"
        elif s == "titres de participation":
            key = "titres_participation"
        elif s == "stocks" or s.startswith("stocks f"):
            key = "stocks"
        elif s == "marchandises":
            key = "marchandises"
        elif "matieres et fournitures consommables" in s:
            key = "matieres_fournitures_consommables"
        elif "creances de l actif circulant" in s:
            key = "creances_actif_circulant"
        elif "fournis" in s and "debiteurs" in s and "acomptes" in s:
            key = "fournisseurs_debiteurs"
        elif s == "clients et comptes rattaches":
            key = "clients"
        elif s == "personnel":
            key = "personnel_debiteur"
        elif s == "etat":
            key = "etat_debiteur"
        elif "comptes d associes" in s:
            key = "comptes_associes_actif"
        elif s == "autres debiteurs":
            key = "autres_debiteurs"
        elif "comptes de regularisation" in s and "actif" in s:
            key = "cca_actif"
        elif "titres valeurs de placement" in s or "titres et valeur de placement" in s:
            key = "titres_valeurs_placement"
        elif s in {"tresorerie actif", "tresorerie actif total"}:
            key = "tresorerie_actif"
        elif "banques" in s and ("c c p" in s or "t g" in s):
            key = "banques_actif"
        elif "caisse" in s and ("regie" in s or "accredit" in s):
            key = "caisse"

    # ---------------------------- BILAN PASSIF ---------------------------
    elif row.section == "bilan_passif":
        if "total general" in n:
            key = "total_passif"
        elif s == "total i" or s.startswith("total i a+b+c+d+e"):
            key = "total_capitaux_permanents"
        elif s == "total ii" or s.startswith("total ii f+g+h"):
            key = "total_passif_circulant"
        elif s == "total iii":
            key = "tresorerie_passif"
        elif s == "capital social ou personnel":
            key = "capital"
        elif s == "reserve legale":
            key = "reserve_legale"
        elif s == "autres reserves":
            key = "autres_reserves"
        elif s == "report a nouveau":
            key = "report_a_nouveau"
        elif "resultat net de l exercice" in s:
            key = "resultat_net"
        elif s.startswith("total des capitaux propres"):
            key = "fonds_propres"
        elif s.startswith("dettes de financement"):
            key = "dettes_financement"
        elif s == "emprunts obligataires":
            key = "emprunts_obligataires"
        elif s == "autres dettes de financement":
            key = "autres_dettes_financement"
        elif "dettes du passif circulant" in s:
            key = "dettes_passif_circulant"
        elif s == "fournisseurs et comptes rattaches":
            key = "fournisseurs"
        elif "clients crediteurs" in s and "acomptes" in s:
            key = "clients_crediteurs"
        elif s == "personnel":
            key = "personnel_crediteur"
        elif s == "organismes sociaux":
            key = "organismes_sociaux"
        elif s == "etat":
            key = "etat_crediteur"
        elif "comptes d associes" in s:
            key = "comptes_associes_passif"
        elif s == "autres creanciers":
            key = "autres_crediteurs"
        elif "comptes de regularisation" in s and "passif" in s:
            key = "cca_passif"
        elif "autres provisions pour risques et charges" in s:
            key = "autres_provisions_risques_charges"
        elif s == "credits d escompte":
            key = "credits_escompte"
        elif s == "credits de tresorerie":
            key = "credits_tresorerie"
        elif s == "banques soldes crediteurs":
            key = "banques_passif"
        elif s == "tresorerie passif":
            key = "tresorerie_passif"

    # ------------------------------- CPC ---------------------------------
    elif row.section == "cpc":
        total_match=re.match(r'^total\s+([ivxlcdm]+|[0-9]+|viie|viiie)\b', s)
        total_token=total_match.group(1) if total_match else None
        total_token={'1':'i','2':'ii','3':'iii','11':'ii','111':'iii','viie':'viii','viiie':'viii'}.get(total_token,total_token)
        if total_token == 'iv':
            key = 'produits_financiers'
        elif total_token == 'v':
            key = 'charges_financieres'
        elif total_token == 'viii':
            key = 'produits_non_courants'
        elif total_token == 'ix':
            key = 'charges_non_courantes'
        elif s == "total i":
            key = "produits_exploitation"
        elif s == "total ii":
            key = "charges_exploitation"
        elif "chiffres d affaires" in s or "chiffre d affaires" in s:
            key = "chiffre_affaires"
        elif "ventes de marchandises" in s:
            key = "ventes_marchandises"
        elif "ventes de biens et services produits" in s:
            key = "ventes_biens_services"
        elif "variation de stocks de produits" in s:
            key = "variation_stock_produits"
        elif "achats revendus" in s and "marchandises" in s:
            key = "achats_rev_marchandises"
        elif "achats consommes" in s and ("matieres" in s or "fournitures" in s):
            key = "achats_consommes"
        elif "autres charges externes" in s:
            key = "autres_charges_externes"
        elif s == "impots et taxes":
            key = "impots_taxes"
        elif "charges de personnel" in s:
            key = "charges_personnel"
        elif "dotations d exploitation" in s:
            key = "dotations_exploitation"
        elif 'resultat' in s and any(t in s for t in ('exploitation','explojtation','exploltation','enplojtation')):
            key = 'resultat_exploitation'
        elif "produits des titres" in s and "particip" in s:
            key = "produits_titres_participation"
        elif "interets et autres produits financiers" in s:
            key = "interets_autres_produits_financiers"
        elif "charges d interets" in s:
            key = "charges_interets"
        elif 'resultat financier' in s:
            key = 'resultat_financier'
        elif 'resultat courant' in s:
            key = 'resultat_courant'
        elif (s.startswith('viii produits non courants') or s.startswith('produits non courants')) and 'resultat' not in s:
            key = 'produits_non_courants'
        elif s.startswith('charges') and 'non' in s and 'courant' in s and not s.startswith('autres charges') and 'resultat' not in s:
            key = 'charges_non_courantes'
        elif "resultat non courant" in s:
            key = "resultat_non_courant"
        elif "resultat avant impots" in s:
            key = "resultat_avant_impots"
        elif "impots sur les resultats" in s:
            key = "impots_resultats"
        elif "resultat net" in s:
            key = "resultat_net"

    # -------------------------------- ESG --------------------------------
    elif row.section == "esg":
        if "autres charges externes" in s:
            key = "autres_charges_externes"
        elif "impots et taxes" in s:
            key = "impots_taxes"
        elif "charges de personnel" in s:
            key = "charges_personnel"
        elif "dotations d exploitation" in s:
            key = "dotations_exploitation"
        elif 'resultat' in s and any(t in s for t in ('exploitation','explojtation','exploltation','enplojtation')):
            key = 'resultat_exploitation'
        elif 'resultat financier' in s:
            key = 'resultat_financier'
        elif 'resultat courant' in s:
            key = 'resultat_courant'
        elif "resultat non courant" in s:
            key = "resultat_non_courant"
        elif "impots sur les resultats" in s:
            key = "impots_resultats"
        elif "resultat net de l exercice" in s:
            key = "resultat_net"
        elif "capacite d autofinancement" in s and "autofinancement" not in s.replace("capacite d autofinancement", ""):
            key = "caf"
        elif s == "autofinancement" or s.endswith("autofinancement"):
            key = "autofinancement"

    # ---------------------------- DETAIL CPC ------------------------------
    elif row.section == "detail_cpc":
        if "locations et charges locatives" in s:
            key = "locations_charges_locatives"
        elif "redevances de credit bail" in s:
            key = "redevances_credit_bail"
        elif "charges de personnel" in s and "total" not in s:
            key = "charges_personnel"
        elif "interets et autres produits financiers" in s:
            key = "interets_autres_produits_financiers"
        elif g == "produits financiers" and s == "total":
            key = "produits_financiers"
        elif g == "charges non courantes" and s == "total":
            key = "charges_non_courantes"
        elif g == "charges d exploitation" and s == "total":
            key = "charges_exploitation"

    if key:
        row.canonical_key = key
        row.mapping_method = method
        row.match_score = score

    return row

TOTAL_KEYS = {
    'bilan_actif': {'i': 'total_immobilise', 'ii': 'total_actif_circulant', 'iii': 'tresorerie_actif'},
    'bilan_passif': {'i': 'total_capitaux_permanents', 'ii': 'total_passif_circulant', 'iii': 'tresorerie_passif'},
    'cpc': {'i': 'produits_exploitation', 'ii': 'charges_exploitation',
            'iv': 'produits_financiers', 'v': 'charges_financieres',
            'viii': 'produits_non_courants', 'ix': 'charges_non_courantes',
            'xiv': 'total_produits', 'xv': 'total_charges'},
}
LABEL_ALIASES = {
    'bilan_actif': {
        'total general i ii iii': 'total_actif',
        'immobilisations en non valeurs a': 'immobilisations_non_valeurs',
        'immobilisations incorporelles b': 'immobilisations_incorporelles',
        'immobilisations corporelles c': 'immobilisations_corporelles',
        'immobilisations financieres d': 'immobilisations_financieres',
        'clients et comptes rattaches': 'clients',
        'titres de participation': 'titres_participation',
        'tresorerie actif': 'tresorerie_actif',
        'banques t g et c c p': 'banques_actif',
        'caisse regie d avances et accreditifs': 'caisse',
        'comptes de regularisation actif': 'cca_actif',
        'charges constatees d avance': 'charges_constatees_avance',
    },
    'bilan_passif': {
        'capital social ou personnel': 'capital',
        'capitaux propres a': 'fonds_propres',
        'total des capitaux propres a': 'fonds_propres',
        'capitaux propres assimiles b': 'capitaux_propres_assimiles',
        'total des capitaux propres assimiles b': 'capitaux_propres_assimiles',
        'resultat net de l exercice': 'resultat_net',
        'fournisseurs et comptes rattaches': 'fournisseurs',
        'comptes d associes': 'comptes_associes_passif',
        'dettes de financement c': 'dettes_financement',
        'banques soldes crediteurs': 'banques_passif',
        'tresorerie passif': 'tresorerie_passif',
    },
    'cpc': {
        'chiffre d affaires': 'chiffre_affaires',
        'chiffres d affaires': 'chiffre_affaires',
        'dont a l exportation': 'chiffre_affaires_export',
        'dont export': 'chiffre_affaires_export',
        'resultat courant': 'resultat_courant',
        'resultat net de l exercice': 'resultat_net',
        'charges d interets': 'charges_interets',
        'achats consommes de matieres et fournitures': 'achats_consommes',
        'achats revendus de marchandises': 'achats_rev_marchandises',
        'autres charges externes': 'autres_charges_externes',
    },
    'esg': {
        'valeur ajoutee': 'valeur_ajoutee',
        'excedent brut d exploitation': 'ebe',
        'insuffisance brute d exploitation': 'ibe',
        'capacite d autofinancement c a f': 'caf',
        'autofinancement': 'autofinancement',
    },
    'detail_cpc': {
        'locations et charges locatives': 'locations_charges_locatives',
        'redevances de credit bail': 'redevances_credit_bail',
    },
}

LABEL_ALIASES['bilan_actif'].update({
    'marchandises':'marchandises','personnel':'personnel_debiteur','etat':'etat_debiteur',
    'autres debiteurs':'autres_debiteurs','stocks':'stocks',
    'mobilier materiel de bureau et amenagement divers':'mobilier_materiel_bureau',
    'titres valeurs de placement h':'titres_valeurs_placement',
    'comptes d associes':'comptes_associes_actif',
})
LABEL_ALIASES['bilan_passif'].update({
    'reserve legale':'reserve_legale','reserves legales':'reserve_legale',
    'report a nouveau':'report_a_nouveau','reports a nouveau':'report_a_nouveau',
    'autres reserves':'autres_reserves','personnel':'personnel_crediteur',
    'organismes sociaux':'organismes_sociaux','etat':'etat_crediteur',
    'autres creanciers':'autres_crediteurs','credits d escompte':'credits_escompte',
    'credits de tresorerie':'credits_tresorerie',
})



def normalize_total_numeral(label: str, section: str) -> str | None:
    """Recover DGI TOTAL I/II/III even when OCR confuses Roman numerals."""
    raw=strip_accents(label or '').lower()
    n=semantic_label(label or '')
    # Printed formula is stronger than the damaged numeral.
    loose_formula=re.search(r'\b([a-h])\s*\+\s*([a-h])(?:\s*\+\s*([a-h]))?(?:\s*\+\s*([a-h]))?',raw)
    if loose_formula and section in {'bilan_actif','bilan_passif'}:
        letters=''.join(x for x in loose_formula.groups() if x)
        if letters=='abcde': return 'i'
        if letters in {'fgh','fghi'}: return 'ii'
    m=re.match(r'^total\s+([^\s(]+)',n)
    if not m: return None
    token=m.group(1)
    aliases={'1':'i','i':'i','l':'i','2':'ii','ii':'ii','11':'ii','il':'ii','i1':'ii',
             '3':'iii','iii':'iii','111':'iii','iil':'iii','ill':'iii','mi':'iii','mii':'iii',
             '1x':'ix','ix':'ix','1v':'iv','iv':'iv','v':'v','viii':'viii','xiv':'xiv','xv':'xv'}
    return aliases.get(token,token if token in {'iv','v','viii','ix','xiv','xv'} else None)

def map_row_strict(row: FinancialRow) -> FinancialRow:
    if row.section not in FINANCIAL_SECTIONS:
        return row
    if any(x in normalize_label(row.label) for x in ['reste du poste', 'detail du poste']):
        return row
    if row.section=='esg' and 'dotations d exploitation' in normalize_label(row.label) and '(+)' in row.label:
        row.canonical_key = 'dotations_exploitation_caf'
        row.mapping_method,row.match_score = 'strict_section_rule',100.0
        return row
    clean = re.sub(r'\(\s*[12]\s*\)', ' ', row.label)
    clean = re.sub(r'(?i)\btotal(?=[IVX123])', 'Total ', clean)
    clean = re.sub(r'(?i)^\s*(?:tetal|tota[)l1])\s+', 'Total ', clean)
    n = semantic_label(clean)
    key = None
    numeral=normalize_total_numeral(clean,row.section) if n.startswith('total') else None
    if numeral is None and 'total' in normalize_label(row.group_label):
        numeral=normalize_total_numeral(row.group_label,row.section)
    if numeral:
        key=TOTAL_KEYS.get(row.section,{}).get(numeral)
        if key:
            row.mapping_method='printed_total_formula_or_ocr_numeral' if row.source_parser.startswith('tesseract') else 'printed_total_numeral'
            row.match_score=100.0 if numeral in {'i','ii','iii','iv','v','viii','ix','xiv','xv'} else 96.0
    elif n.startswith('total general'):
        key = {'bilan_actif': 'total_actif', 'bilan_passif': 'total_passif'}.get(row.section)
    else:
        if row.section == 'cpc' and n.startswith('autres produits non courants'):
            row.canonical_key = 'autres_produits_non_courants'
            row.mapping_method, row.match_score = 'strict_section_rule',100.0
            return row
        if row.section == 'bilan_actif' and n.startswith('immobilisations corporelles en cours'):
            row.canonical_key = 'immobilisations_corporelles_en_cours'
            row.mapping_method, row.match_score = 'strict_section_rule',100.0
            return row
        probe = dataclasses.replace(row, label=clean, canonical_key=None)
        # Detail-CPC totals are individual subheadings, not whole-CPC totals.
        if not (row.section == 'detail_cpc' and n == 'total'):
            probe = _legacy_section_rules(probe)
            key = probe.canonical_key
        aliases = LABEL_ALIASES.get(row.section, {})
        if not key:
            for label, candidate in aliases.items():
                if n == label or (len(label) >= 12 and n.startswith(label + ' ')) or (n.startswith(label+' ') and all(len(t)<=2 for t in n[len(label):].split())):
                    key = candidate
                    break
        if not key and row.source_parser.startswith('tesseract') and len(n) >= 14:
            # Fuzzy matching only for a short, section-scoped alias list.
            # Never use it for Roman totals, short words, or numeric values.
            scores = sorted(((SequenceMatcher(None, n, label).ratio(), key, label)
                             for label, key in aliases.items()
                             if not label.startswith('total ')), reverse=True)
            if scores and scores[0][0] >= .92:
                different = next((s[0] for s in scores[1:] if s[1] != scores[0][1]), 0)
                if scores[0][0] - different >= .06:
                    key = scores[0][1]
                    row.mapping_method = 'section_alias_ocr'
                    row.match_score = round(scores[0][0] * 100, 2)
                    row.warnings.append('OCR_label_alias:' + scores[0][2])
    if key:
        row.canonical_key = key
        row.mapping_method = row.mapping_method or 'strict_section_rule'
        row.match_score = row.match_score if row.match_score is not None else 100.0
    return row


def line_groups(words: list[dict], tolerance: float | None = None) -> list[list[dict]]:
    if not words:
        return []
    tolerance = tolerance or max(2, statistics.median(w['bbox'][3]-w['bbox'][1] for w in words) * .45)
    groups: list[list[dict]] = []
    for word in sorted(words, key=lambda w: ((w['bbox'][1]+w['bbox'][3])/2, w['bbox'][0])):
        y = (word['bbox'][1]+word['bbox'][3])/2
        if not groups or abs(y-statistics.mean((w['bbox'][1]+w['bbox'][3])/2 for w in groups[-1])) > tolerance:
            groups.append([])
        groups[-1].append(word)
    return [sorted(g, key=lambda w: w['bbox'][0]) for g in groups]


def words_text(words: list[dict]) -> str:
    return '\n'.join(' '.join(w['text'] for w in group) for group in line_groups(words))


def clean_identity(text: str) -> dict:
    # Keep exact dates from the document; never use the PDF's filename year.
    text = text.replace('|', ' ')
    identity = dataclasses.asdict(extract_identity_from_text(text))
    for key in ['raison_sociale', 'adresse', 'ville', 'activite']:
        v = identity[key]
        if v:
            v = re.split(r'\b(?:ICE|Identifiant fiscal|Art\.? Taxe professionnelle|Ville|Activit[ée])\s*:', v, flags=re.I)[0].strip()
            if normalize_label(v) in {'ville', 'adresse', 'activite', 'raison sociale'}:
                v = None
            identity[key] = v
    identity['evidence'] = {k:v for k,v in identity['evidence'].items()
                            if k == 'period' or identity.get(k) == v}
    for key in ['period_start', 'period_end', 'declaration_date']:
        if identity[key]:
            try:
                datetime.strptime(identity[key], '%d/%m/%Y')
            except ValueError:
                identity[key] = None
    return identity


def identify_schema(matrix: list[list[dict]], section: str) -> tuple[dict[str, int], int, str]:
    if not matrix or section not in FINANCIAL_SECTIONS:
        return {}, 0, 'unresolved'
    width = len(matrix[0])
    # Inspect header rows only. A body row containing "résultat de l'exercice"
    # must never become a column header and cause preceding rows to disappear.
    headers = [' '.join(matrix[r][c]['text'] for r in range(min(2, len(matrix)))) for c in range(width)]
    n = [normalize_label(h) for h in headers]
    start = 0
    if any(('exercice' in c or 'brut' in c or 'precedent' in c) for c in n[-min(4,width):]):
        start = 1
    schema: dict[str, int] = {}
    if section in {'bilan_actif', 'cpc'} and width >= 5:
        # Known DGI layout: 1 or 2 text columns followed by FOUR distinct
        # amount columns. Blank cells remain in their original position.
        keys = ['brut_current', 'amort_prov_current', 'current', 'previous'] if section == 'bilan_actif' else ['operations_current', 'operations_prior_period', 'current', 'previous']
        schema = dict(zip(keys, range(width-4, width)))
        method = 'dgi_four_amount_columns'
    elif section in {'bilan_passif','esg','detail_cpc'} and width >= 3:
        schema = {'current': width-2, 'previous': width-1}
        method = 'two_amount_columns'
    elif section == 'cpc' and width in (3,4):
        schema = {'current': width-2, 'previous': width-1}
        method = 'cpc_two_amount_columns'
    else:
        return {}, start, 'unresolved'
    # Honor explicit headers when available; cannot assign one column twice.
    if 'previous' in schema:
        previous = [i for i in schema.values() if 'precedent' in n[i] and 'concernant' not in n[i]]
        if len(previous) == 1:
            old_previous = schema['previous']
            if previous[0] != old_previous:
                other = next((k for k,v in schema.items() if v == previous[0]), None)
                if other:
                    schema[other] = old_previous
                schema['previous'] = previous[0]
                method += '_explicit_previous_header'
    return schema, start, method


def rows_from_cells(table: dict, section: str, page_number: int, parser: str,
                    min_confidence: float = 60) -> tuple[list[FinancialRow], dict]:
    matrix = table['cells']
    schema, start, method = identify_schema(matrix, section)
    diagnostic = {'table_id': table['table_id'], 'bbox': table['bbox'], 'schema': schema,
                  'schema_method': method, 'rows': len(matrix), 'columns': len(matrix[0]) if matrix else 0}
    if not schema:
        return [], diagnostic
    rows = []
    label_columns = list(range(min(schema.values())))
    for index in range(start, len(matrix)):
        cells = matrix[index]
        text_cells = [(i, cells[i]['text'].strip()) for i in label_columns if len(normalize_label(cells[i]['text'])) >= 3]
        if not text_cells:
            continue
        label_index, label = text_cells[-1]
        group = text_cells[0][1] if len(text_cells) > 1 else ''
        if len(normalize_label(label)) < 3:
            continue
        row = FinancialRow(page=page_number, section=section, group_label=group, label=compact_text(label),
                           source_parser=parser, table_id=table['table_id'], row_index=index,
                           raw=' | '.join(c['text'] for c in cells))
        row.evidence['label'] = {'raw': label, 'bbox': cells[label_index].get('bbox'),
                                 'coordinate_space': table['coordinate_space']}
        row.evidence['schema'] = method
        confidences = []
        for name, column in schema.items():
            cell = cells[column]
            parsed = parse_amount_ocr_relaxed(cell['text']) if parser.startswith('tesseract') else parse_amount(cell['text'])
            if cell.get('missing_geometry'):
                parsed['status'] = 'missing_cell'
                parsed['value'] = None
            if cell.get('format_issue'):
                parsed.update(status='unparsed',value=None)
            conf = cell.get('confidence', 100.0)
            if conf is not None and parsed['value'] is not None:
                confidences.append(conf / 100)
                if conf < min_confidence:
                    row.warnings.append('low_ocr_confidence:' + name)
                    parsed['status'] = 'low_confidence'
            if parsed['repairs']:
                row.warnings.append('repaired_numeric_text:' + name)
            if parsed['status'] == 'unparsed':
                row.warnings.append('unparsed_cell:' + name)
            parsed.update(bbox=cell.get('bbox'), confidence=conf, column_index=column,
                          coordinate_space=table['coordinate_space'])
            if cell.get('ocr_attempts'):
                parsed['ocr_attempts'] = cell['ocr_attempts']
            if cell.get('unicode_sign_recovery'):
                parsed['unicode_sign_recovery']=cell['unicode_sign_recovery']
            if cell.get('reading_selection'):
                parsed['reading_selection'] = cell['reading_selection']
                parsed['original_raw'] = cell.get('original_text')
                if cell.get('original_text') != cell['text']:
                    parsed['repairs'].append('explicit_local_ocr_reading_selection')
            if cell.get('structural_repair'):
                parsed['structural_repair']=cell['structural_repair']
            row.evidence[name] = parsed
            setattr(row, name, parsed['value'])
        row.confidence = round(min(confidences, default=.98 if parser == 'pymupdf' else .65), 4)
        rows.append(map_row_strict(row))
    return rows, diagnostic


def recover_section(table: dict, parser: str) -> str:
    """Recover a damaged title from several distinct financial row labels."""
    scores = []
    for section in FINANCIAL_SECTIONS:
        schema,_,_ = identify_schema(table['cells'],section)
        if not schema:
            continue
        # A four-value table is never a two-period passif/ESG table.
        width = len(table['cells'][0])
        if width >= 5 and section not in {'bilan_actif','cpc'}:
            continue
        keys = set()
        for cells in table['cells']:
            labels = [c['text'] for c in cells[:min(schema.values())] if len(normalize_label(c['text']))>=3]
            if labels:
                probe = map_row_strict(FinancialRow(0,section,'',labels[-1],source_parser=parser))
                if probe.canonical_key:
                    keys.add(probe.canonical_key)
        scores.append((len(keys),section))
    scores.sort(reverse=True)
    if scores and scores[0][0]>=4 and (len(scores)==1 or scores[0][0]-scores[1][0]>=2):
        return scores[0][1]
    return 'generic'


def native_page(page: fitz.Page, page_number: int, config: Config) -> dict:
    words = [{'text':w[4], 'bbox':list(w[:4]), 'confidence':100.0} for w in page.get_text('words')]
    text = words_text(words)
    # Only titles identify the document section; table-local cues can recover
    # absent titles without inheriting an unrelated preceding appendix.
    title = words_text([w for w in words if w['bbox'][1] < page.rect.height*.20])
    section = detect_section(title)
    tables, rows, diags, errors = [], [], [], []
    try:
        with contextlib.redirect_stdout(sys.stderr):
            finder = page.find_tables()
        for table_id, table in enumerate(finder.tables):
            raw = table.extract()
            if table.row_count < 2:
                continue
            matrix = []
            for r, texts in enumerate(raw):
                matrix.append([{'text': texts[c] or '',
                                'bbox': list(table.rows[r].cells[c]) if table.rows[r].cells[c] is not None else None,
                                'missing_geometry': table.rows[r].cells[c] is None,
                                'confidence':100.0} for c in range(table.col_count)])
            record = {'table_id':table_id, 'bbox':list(table.bbox), 'cells':matrix,
                      'coordinate_space':'pdf_points_unrotated'}
            local = section if section != 'generic' else detect_section(' '.join(c['text'] for r in matrix for c in r))
            if local == 'generic':
                local = recover_section(record,'pymupdf')
            record['section'] = local
            repair_merged_two_period_rows(record,local)
            rr, dd = rows_from_cells(record, local, page_number, 'pymupdf', config.min_ocr_confidence)
            tables.append(record); rows.extend(rr); diags.append(dd)
            if section == 'generic' and local in FINANCIAL_SECTIONS:
                section = local
    except Exception as exc:
        errors.append('native_table_error:' + str(exc))
    return {'page':page_number, 'kind':'native', 'parser':'pymupdf', 'section':section,
            'text':text, 'rows':[dataclasses.asdict(r) for r in rows], 'tables':tables,
            'table_diagnostics':diags, 'errors':errors, 'rotation_clockwise':0,
            'native_word_count':len(words)}


def tesseract_info(config: Config) -> dict:
    binary = shutil.which(config.tesseract_cmd)
    if not binary:
        raise RuntimeError('Tesseract introuvable. Installez le programme ou utilisez --tesseract-cmd.')
    env = {**os.environ, 'OMP_THREAD_LIMIT':'1'}
    version = subprocess.run([binary, '--version'], capture_output=True, text=True, check=True,
                             timeout=10, env=env).stdout.splitlines()[0]
    langs = subprocess.run([binary, '--list-langs'], capture_output=True, text=True, check=True,
                           timeout=10, env=env).stdout.splitlines()[1:]
    requested = config.ocr_language.split('+')
    missing = [lang for lang in requested if lang not in langs]
    if missing:
        raise RuntimeError('Langues OCR absentes : ' + ', '.join(missing) + '. Installez-les ou passez --ocr-language eng.')
    return {'version':version, 'languages':requested}


def tesseract(image, config: Config, *, psm: int = 6, offset=(0,0), osd: bool = False, numeric: bool = False) -> Any:
    import cv2
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise RuntimeError('Image OCR non encodable')
    args = [config.tesseract_cmd, 'stdin', 'stdout', '-l', 'osd' if osd else config.ocr_language,
            '--psm', str(psm), '--dpi', str(config.dpi)]
    if not osd:
        if numeric:
            args += ['-c', 'tessedit_char_whitelist=0123456789.,()+-']
        args += ['-c','tessedit_create_tsv=1']
    process = subprocess.run(args, input=data.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=config.ocr_timeout, env={**os.environ, 'OMP_THREAD_LIMIT':'1'})
    if process.returncode:
        raise RuntimeError(process.stderr.decode('utf-8', errors='replace')[-700:])
    output = process.stdout.decode('utf-8', errors='replace')
    if osd:
        return output
    if output.strip() and not output.startswith('level\tpage_num\t'):
        raise RuntimeError('Tesseract did not return TSV; check engine configuration: '+process.stderr.decode('utf-8',errors='replace')[-300:])
    words = []
    for row in csv.DictReader(io.StringIO(output), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row.get('level') != '5' or not row.get('text','').strip():
            continue
        try:
            x,y,w,h = [int(row[k]) for k in ('left','top','width','height')]
            words.append({'text':row['text'].strip(), 'bbox':[x+offset[0],y+offset[1],x+w+offset[0],y+h+offset[1]],
                          'confidence':float(row['conf'])})
        except (ValueError, TypeError):
            continue
    return words


def rotate_image(image, clockwise: int):
    import numpy as np
    return np.ascontiguousarray(np.rot90(image, -(clockwise//90)))


def orientation(image, config: Config) -> tuple[int, list[dict]]:
    import cv2
    if config.rotation is not None:
        return config.rotation, [{'method':'user_override', 'rotation':config.rotation}]
    height,width = image.shape[:2]
    scale = min(1., 1800/max(height,width))
    thumb = cv2.resize(image, None, fx=scale, fy=scale)
    candidates = []
    first = 0
    try:
        osd = tesseract(thumb, config, psm=0, osd=True)
        rotation = re.search(r'Rotate:\s*(\d+)', osd)
        confidence = re.search(r'Orientation confidence:\s*([\d.]+)', osd)
        if rotation:
            first = int(rotation[1])
        if rotation and confidence and float(confidence[1]) >= 5:
            return first, [{'method':'tesseract_osd', 'rotation':first, 'confidence':float(confidence[1])}]
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    # A tiny preview is enough to disambiguate ordinary French text. Financial
    # titles and language score matter more than the mere number of numbers.
    for angle in dict.fromkeys([first, 0, 90, 270, 180]):
        try:
            words = tesseract(rotate_image(thumb, angle), config, psm=11)
            text = normalize_label(words_text(words))
            hits = sum(text.count(k) for k in ['exercice','bilan','actif','passif','total','declaration',
                      'raison sociale','produits','charges','resultat','immobilisations','comptes','fiscal'])
            alpha = [w for w in words if re.search(r'[A-Za-z]{3}',w['text'])]
            conf = statistics.mean(w['confidence'] for w in alpha) if alpha else 0
            score = hits*4 + conf*.1
            candidates.append({'method':'preview_text', 'rotation':angle, 'score':round(score,2)})
            if hits >= 7 and conf >= 65:
                break
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            candidates.append({'rotation':angle, 'error':str(exc)[:200], 'score':-1})
    return max(candidates, key=lambda d:d.get('score',-1))['rotation'] if candidates else first, candidates


def deskew(image) -> tuple[Any, float]:
    import cv2
    import numpy as np
    scale = min(1., 1800/max(image.shape))
    small = cv2.resize(image, None, fx=scale, fy=scale)
    edges = cv2.Canny(small, 80, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi/1800, threshold=100,
                            minLineLength=max(100,int(small.shape[1]*.18)), maxLineGap=15)
    angles = []
    if lines is not None:
        for line in lines.reshape(-1,4):
            x1,y1,x2,y2 = line
            angle = math.degrees(math.atan2(y2-y1,x2-x1))
            if abs(angle) < 4:
                angles.append(angle)
    angle = statistics.median(angles) if len(angles) >= 3 else 0.
    if abs(angle) < .08:
        return image, 0.
    h,w = image.shape[:2]
    transform = cv2.getRotationMatrix2D((w/2,h/2),angle,1.)
    return cv2.warpAffine(image,transform,(w,h),flags=cv2.INTER_CUBIC,borderValue=255),round(angle,4)


def group_positions(values) -> list[int]:
    groups = []
    for v in values:
        if not groups or v > groups[-1][-1]+2:
            groups.append([])
        groups[-1].append(int(v))
    return [round(statistics.mean(g)) for g in groups]


def detect_grids(image) -> tuple[Any, list[dict]]:
    import cv2
    import numpy as np
    # Local thresholding removes shaded cell backgrounds and fax noise while
    # preserving pale grid rules; global Otsu can turn whole headers to ink.
    denoised = cv2.medianBlur(image,3)
    binary = cv2.adaptiveThreshold(denoised,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV,71,18)
    h,w = image.shape
    horizontal = cv2.morphologyEx(binary,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(40,w//50),1)))
    vertical = cv2.morphologyEx(binary,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(40,h//50))))
    mask = cv2.bitwise_or(horizontal,vertical)
    clean = cv2.bitwise_not(binary)
    clean[cv2.dilate(mask, np.ones((3,3),np.uint8))>0] = 255
    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    grids = []
    for c in contours:
        x,y,cw,ch = cv2.boundingRect(c)
        if cw < w*.20 or ch < h*.045 or cw*ch < w*h*.008:
            continue
        xs = group_positions(np.flatnonzero((vertical[y:y+ch,x:x+cw]>0).sum(axis=0) > ch*.30))
        merged = []
        for pos in xs:
            if merged and pos-merged[-1] < max(8,w*.006):
                merged[-1] = round((merged[-1]+pos)/2)
            else:
                merged.append(pos)
        xs = merged
        geometry_method='vertical_rule_projection'
        if len(xs)<4:
            # Faded/slightly slanted rules spread their support over nearby x.
            # Apply only when strict geometry failed; never change a valid grid.
            projection=(vertical[y:y+ch,x:x+cw]>0).sum(axis=0)
            window=max(7,int(w*.0045))|1
            support=np.convolve(projection,np.ones(window),mode='same')
            tolerant=group_positions(np.flatnonzero(support>ch*.60))
            if 4<=len(tolerant)<=12:
                xs=tolerant;geometry_method='local_support_for_faded_vertical_rules'
        ys = group_positions(np.flatnonzero((horizontal[y:y+ch,x:x+cw]>0).sum(axis=1) > cw*.42))
        if not 4 <= len(xs) <= 12 or len(ys) < 3:
            continue
        # A faded outer rule must not truncate the bottom half of a table.
        if ys[0]>8:
            ys.insert(0,0)
        if ch-1-ys[-1]>8:
            ys.append(ch-1)
        # Keep actual geometry, including blank separator rows.
        grids.append({'xs':[x+v for v in xs], 'ys':[y+v for v in ys], 'bbox':[x,y,x+cw,y+ch],'geometry_method':geometry_method})
    return clean, sorted(grids, key=lambda g:(g['bbox'][1],g['bbox'][0]))


def ocr_grid(clean, grid: dict, config: Config, table_id: int) -> dict:
    import cv2
    xs,ys = grid['xs'],grid['ys']
    matrix = [[{'text':'','bbox':[xa,ya,xb,yb],'confidence':None} for xa,xb in zip(xs,xs[1:])]
              for ya,yb in zip(ys,ys[1:])]
    all_column_words = []
    for column,(left,right) in enumerate(zip(xs,xs[1:])):
        # White padding prevents Tesseract from clipping a letter at the edge.
        # A 1 px inset avoids a residual rule without cutting leading digits.
        x0,y0 = left+1,ys[0]+1
        crop = clean[y0:ys[-1],x0:right]
        if not crop.size:
            continue
        padded = cv2.copyMakeBorder(crop,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
        words = tesseract(padded,config,psm=6,offset=(x0-12,y0-12))
        all_column_words.append(words)
        assignments = defaultdict(list)
        for word in words:
            yc = (word['bbox'][1]+word['bbox'][3])/2
            row = bisect.bisect_right(ys,yc)-1
            if 0 <= row < len(matrix):
                assignments[row].append(word)
        for row,ww in assignments.items():
            matrix[row][column]['text'] = words_text(ww)
            matrix[row][column]['confidence'] = min(w['confidence'] for w in ww)
    # Forms with only subtotal rules have several physical lines inside a
    # single geometric cell. Split them by label baselines before assigning
    # amounts, instead of flattening all values into one unparseable string.
    if len(all_column_words) == len(xs)-1:
        width = len(xs)-1
        candidates = list(range(max(1,width-(4 if width>=5 else 2))))
        label_col = max(candidates,key=lambda i:sum(len(w['text']) for w in all_column_words[i]
                        if re.search('[A-Za-z]{3}',w['text'])))
        new_ys = list(ys)
        for top,bottom in zip(ys,ys[1:]):
            numeric_lines = []
            for words in all_column_words[-2:]:
                groups = line_groups([w for w in words if top<(w['bbox'][1]+w['bbox'][3])/2<bottom])
                numeric_lines.extend(groups)
            if max((len(line_groups([w for w in words if top<(w['bbox'][1]+w['bbox'][3])/2<bottom])) for words in all_column_words[-2:]), default=0)<2:
                continue
            lines = line_groups([w for w in all_column_words[label_col]
                                 if top<(w['bbox'][1]+w['bbox'][3])/2<bottom])
            previous = None
            for line in lines:
                text = ' '.join(w['text'] for w in line).strip()
                # Wrapped label continuations must stay in the same row.
                continuation = bool(re.match(r'(?i)^(?:et |en cours|am[eé]nagement|exercices?$|similaires$|rattach[eé]s$|obligations$|d[eé]veloppement$|\([A-I]\)$)',text))
                y = statistics.mean((w['bbox'][1]+w['bbox'][3])/2 for w in line)
                if previous is not None and not continuation:
                    new_ys.append(round((previous+y)/2))
                previous = y
        refined = sorted(set(new_ys))
        if len(refined)>len(ys):
            ys = refined
            matrix = [[{'text':'','bbox':[xa,ya,xb,yb],'confidence':None} for xa,xb in zip(xs,xs[1:])]
                      for ya,yb in zip(ys,ys[1:])]
            for column,words in enumerate(all_column_words):
                assigned = defaultdict(list)
                for word in words:
                    row = bisect.bisect_right(ys,(word['bbox'][1]+word['bbox'][3])/2)-1
                    if 0<=row<len(matrix):
                        assigned[row].append(word)
                for row,ww in assigned.items():
                    matrix[row][column]['text'] = words_text(ww)
                    matrix[row][column]['confidence'] = min(w['confidence'] for w in ww)
    return {'table_id':table_id,'bbox':grid['bbox'],'cells':matrix,'geometry_method':grid.get('geometry_method'),
            'coordinate_space':'ocr_pixels_after_rotation_and_deskew'}


def retry_numeric_cells(clean, table: dict, section: str, config: Config, *, checking_rows: bool = False) -> None:
    """Re-read uncertain numeric cells locally without arithmetic imputation.

    V6 selection is deliberately conservative: a low-confidence parseable retry
    cannot replace a high-confidence but ambiguous original reading unless the
    retry is independently corroborated by another OCR attempt.  Harmless outer
    punctuation is tolerated, but missing digits are never guessed.
    """
    import cv2
    schema,start,_ = identify_schema(table['cells'],section)
    decimal_columns = set()
    for column in schema.values():
        texts = [r[column]['text'].strip() for r in table['cells'][start:] if re.search(r'\d',r[column]['text'])]
        decimal_count = sum(bool(re.search(r'[.,]\d{2}\s*[)\-]?$',t)) for t in texts)
        if decimal_count>=3 and decimal_count/max(1,len(texts))>=.7:
            decimal_columns.add(column)

    def parsed_attempt(a):
        return parse_amount_ocr_relaxed(a.get('text'))

    for cells in table['cells'][start:]:
        for column in schema.values():
            cell = cells[column]
            original = parse_amount_ocr_relaxed(cell['text'])
            confidence = cell.get('confidence')
            missing_decimal = column in decimal_columns and original['value'] not in {None,'0','0.00'} and not re.search(r'[.,]',cell['text'])
            if original['status'] in {'blank','dash'}:
                continue
            if checking_rows and not cell.get('force_retry'):
                continue
            if original['value'] is not None and confidence is not None and confidence >= config.min_ocr_confidence and not missing_decimal and not cell.get('force_retry'):
                continue
            left,top,right,bottom = map(int,cell['bbox'])
            crop = clean[top+1:bottom,left+1:right]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
            crop = cv2.copyMakeBorder(crop,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
            attempts = [{'text':cell['text'],'confidence':confidence,'method':'column_psm6'}]
            for psm in (7,13):
                words = tesseract(crop,config,psm=psm,numeric=True)
                text = words_text(words)
                conf = min((w['confidence'] for w in words),default=0)
                attempts.append({'text':text,'confidence':conf,'method':f'cell_psm{psm}'})
                parsed = parse_amount_ocr_relaxed(text)
                if parsed['value'] is not None and conf >= 80 and not cell.get('force_retry'):
                    break

            for a in attempts:
                parsed=parsed_attempt(a)
                a.update(value=parsed['value'],parser='tesseract',repairs=parsed.get('repairs',[]))

            valid=[a for a in attempts if a['value'] is not None]
            if valid:
                counts=defaultdict(int)
                for a in valid:
                    counts[Decimal(a['value'])]+=1
                original_conf=float(confidence or 0)
                original_parsed=parsed_attempt(attempts[0])

                def score(a):
                    votes=counts[Decimal(a['value'])]
                    conf=float(a.get('confidence') or 0)
                    is_original=a is attempts[0]
                    # Candidate credibility: votes dominate, then confidence.
                    # Preserve a valid original unless another reading is clearly stronger.
                    return (votes, conf>=config.min_ocr_confidence, conf, is_original)

                best=max(valid,key=score)
                credible=(counts[Decimal(best['value'])]>=2 or float(best.get('confidence') or 0)>=45)
                # If the original OCR is high-confidence but unparseable, do NOT accept a
                # zero/very-low-confidence numeric hallucination.  Keep the original cell
                # unparsed and let targeted verification handle it.
                if original_parsed['value'] is None and original_conf>=config.min_ocr_confidence and not credible:
                    best=None
                # If the original is already a good numeric reading, require independent
                # support or substantially better confidence before replacing it.
                if best is not None and original_parsed['value'] is not None and best is not attempts[0]:
                    if counts[Decimal(best['value'])] < 2 and float(best.get('confidence') or 0) < original_conf + 15:
                        best=attempts[0]

                if best is not None:
                    cell.setdefault('original_text',cell['text'])
                    cell['reading_selection'] = {
                        'original_raw':cell['original_text'],'selected_raw':best['text'],
                        'method':best['method'],'reason':'local_ocr_consensus_confidence_guarded',
                        'arithmetic_used':False,'votes':counts[Decimal(best['value'])],
                        'selected_confidence':best.get('confidence')}
                    cell['text'],cell['confidence'] = best['text'],best['confidence']
                    if best.get('repairs'):
                        cell['reading_selection']['text_repairs']=best['repairs']

            parsed_now=parse_amount_ocr_relaxed(cell['text'])
            if column in decimal_columns and not re.search(r'[.,]',cell['text']) and parsed_now['value'] not in {None,'0','0.00'}:
                cell['format_issue'] = 'missing_decimal_separator_in_decimal_column'
            cell.setdefault('ocr_attempts',[]).extend(attempts)

    if not checking_rows and section in {'bilan_actif','cpc'} and len(schema)==4:
        names = ['brut_current','amort_prov_current','current'] if section=='bilan_actif' else ['operations_current','operations_prior_period','current']
        retry = False
        for cells in table['cells'][start:]:
            values = [decimal_or_none(parse_amount_ocr_relaxed(cells[schema[n]]['text'])['value']) for n in names]
            if any(v is None for v in values):
                continue
            difference = values[0]-values[1]-values[2] if section=='bilan_actif' else values[0]+values[1]-values[2]
            if abs(difference)>Decimal('.02'):
                for name in names:
                    cells[schema[name]]['force_retry'] = True
                retry = True
        if retry:
            retry_numeric_cells(clean,table,section,config,checking_rows=True)


def repair_merged_two_period_rows(table: dict, section: str) -> int:
    """Recover DGI two-period rows when OCR merged both amounts into one cell.

    Example: [blank, "I. CAPACITE D'AUTOFINANCEMENT", "6 088 444,66 5 288 459,72"]
    becomes [label, current, previous].  The rule requires exactly two amounts
    in the right-most cell and a non-numeric label in the middle cell.
    """
    if section not in {'bilan_passif','esg','detail_cpc'}:
        return 0
    matrix=table.get('cells') or []
    if not matrix or len(matrix[0])!=3:
        return 0
    changed=0
    for row in matrix:
        if len(row)!=3: continue
        left,mid,right=row
        if left.get('text','').strip():
            continue
        label=mid.get('text','').strip()
        if len(normalize_label(label))<3 or parse_amount_ocr_relaxed(label)['value'] is not None:
            continue
        tokens=extract_amount_tokens(right.get('text',''),max_tokens=3)
        if len(tokens)!=2:
            continue
        # Avoid interpreting identifiers / dates as amounts.
        if any(abs(Decimal(t['value']))>Decimal('10000000000000') for t in tokens):
            continue
        original_right=dict(right)
        label_cell=dict(mid)
        label_cell['text']=label
        label_cell['structural_repair']='label_shifted_from_middle_column'
        current=dict(right); previous=dict(right)
        current['text']=tokens[0]['raw']; previous['text']=tokens[1]['raw']
        current['structural_repair']='split_merged_current_previous'
        previous['structural_repair']='split_merged_current_previous'
        current['original_text']=original_right.get('text','')
        previous['original_text']=original_right.get('text','')
        bbox=original_right.get('bbox')
        if bbox and len(bbox)==4:
            x0,y0,x1,y1=bbox; xm=(x0+x1)/2
            current['bbox']=[x0,y0,xm,y1]; previous['bbox']=[xm,y0,x1,y1]
        row[0],row[1],row[2]=label_cell,current,previous
        changed+=1
    if changed:
        table.setdefault('structural_repairs',[]).append({'type':'merged_two_period_rows','count':changed})
    return changed

def unruled_table(words: list[dict], image_shape: tuple, section: str) -> dict | None:
    """Two-period unruled statements, anchored by recurring right edges.

    This fallback requires two independently supported amount columns. It
    refuses a guessed schema when only one period is readable.
    """
    if section not in {'bilan_passif','esg','detail_cpc'}:
        return None
    height,width = image_shape
    lines = line_groups(words)
    amounts = []
    for line in lines:
        group = []
        def finish():
            if not group:
                return
            text = ' '.join(w['text'] for w in group)
            box = [min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),
                   max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)]
            if parse_amount(text)['value'] is not None and box[2]>width*.50 and box[1]>height*.10:
                amounts.append({'text':text,'bbox':box,'confidence':min(w['confidence'] for w in group)})
        for word in line:
            numeric = bool(re.fullmatch(r'[\d\s.,()+\-]+',word['text']))
            if numeric and (not group or word['bbox'][0]-group[-1]['bbox'][2] < (word['bbox'][3]-word['bbox'][1])*1.3):
                group.append(word)
            else:
                finish();group = [word] if numeric else []
        finish()
    clusters = []
    for amount in sorted(amounts,key=lambda a:a['bbox'][2]):
        if not clusters or amount['bbox'][2]-statistics.mean(a['bbox'][2] for a in clusters[-1]) > width*.012:
            clusters.append([])
        clusters[-1].append(amount)
    strong = sorted([c for c in clusters if len(c)>=3],key=len,reverse=True)[:2]
    if len(strong)!=2:
        return None
    strong.sort(key=lambda c:statistics.mean(a['bbox'][2] for a in c))
    ends = [statistics.mean(a['bbox'][2] for a in c) for c in strong]
    if ends[1]-ends[0]<width*.07:
        return None
    left = min(a['bbox'][0] for a in strong[0])-width*.008
    middle = (ends[0]+ends[1])/2
    matrix = []
    for line in lines:
        yc = statistics.mean((w['bbox'][1]+w['bbox'][3])/2 for w in line)
        labels = [w for w in line if w['bbox'][2]<left]
        if not labels or yc<height*.10 or yc>height*.92:
            continue
        text = words_text(labels)
        if len(normalize_label(text))<3:
            continue
        top,bottom = min(w['bbox'][1] for w in line)-3,max(w['bbox'][3] for w in line)+3
        cells = [{'text':text,'bbox':[0,top,left,bottom],'confidence':min(w['confidence'] for w in labels)}]
        for lo,hi in [(left,middle),(middle,width)]:
            matched = [w for w in line if lo<=w['bbox'][2]<=hi and w['bbox'][0]>=left]
            cells.append({'text':words_text(matched),'bbox':[lo,top,hi,bottom],
                          'confidence':min((w['confidence'] for w in matched),default=None)})
        matrix.append(cells)
    if len(matrix)<5:
        return None
    return {'table_id':0,'bbox':[0,0,width,height],'cells':matrix,
            'coordinate_space':'ocr_pixels_after_rotation_and_deskew','geometry_method':'recurring_amount_right_edges'}


def scan_page_tesseract(page: fitz.Page, page_number: int, config: Config) -> dict:
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    pix = page.get_pixmap(dpi=config.dpi,colorspace=fitz.csGRAY,alpha=False)
    if pix.width*pix.height > 60_000_000:
        raise RuntimeError('Page trop grande au DPI demandé (>60 millions de pixels). Réduisez --dpi.')
    image = np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width).copy()
    rotation,candidates = orientation(image,config)
    upright,angle = deskew(rotate_image(image,rotation))
    clean,grids = detect_grids(upright)
    # Full-page text is for titles and identity. Numeric data are read from
    # separate table columns, never flattened into a Markdown row.
    scale = min(1.,2400/max(clean.shape))
    preview = cv2.resize(clean,None,fx=scale,fy=scale)
    text_words = tesseract(preview,config,psm=11)
    text = words_text(text_words)
    top = words_text([w for w in text_words if w['bbox'][1] < preview.shape[0]*.19])
    section = classify_page_structure(text,detect_section(top))
    tables,rows,diags,errors = [],[],[],[]
    for table_id,grid in enumerate(grids):
        try:
            table = ocr_grid(clean,grid,config,table_id)
            flat = ' '.join(c['text'] for r in table['cells'] for c in r)
            local = section if section != 'generic' else detect_section(flat)
            if local == 'generic' or (local in FINANCIAL_SECTIONS and not identify_schema(table['cells'],local)[0]):
                local = recover_section(table,'tesseract_grid')
            table['section'] = local
            repair_merged_two_period_rows(table,local)
            retry_numeric_cells(clean,table,local,config)
            rr,dd = rows_from_cells(table,local,page_number,'tesseract_grid',config.min_ocr_confidence)
            tables.append(table); rows.extend(rr); diags.append(dd)
            if local in FINANCIAL_SECTIONS:
                section = local
        except (RuntimeError,subprocess.TimeoutExpired) as exc:
            errors.append('table_ocr_error:' + str(exc)[:500])
    if not rows and section in {'bilan_passif','esg','detail_cpc'}:
        full_words = tesseract(clean,config,psm=11)
        table = unruled_table(full_words,clean.shape,section)
        if table:
            table['section'] = section
            retry_numeric_cells(clean,table,section,config)
            rr,dd = rows_from_cells(table,section,page_number,'tesseract_geometry',config.min_ocr_confidence)
            tables.append(table); rows.extend(rr); diags.append(dd)
    if section in FINANCIAL_SECTIONS and not rows:
        errors.append('financial_table_unresolved')
    elif section == 'generic' and not grids and len(text)>1500 and sum(k in normalize_label(text) for k in ['immobilisations','capitaux','creances','dettes','produits','charges','resultat','exercice'])>=5:
        errors.append('possible_financial_page_without_resolved_grid')
    # Identity pages need the full resolution, because tax IDs are small.
    if page_number == 1 or 'raison sociale' in normalize_label(top):
        identity_words = tesseract(clean,config,psm=11)
        text = words_text(identity_words)
    return {'page':page_number,'kind':'scan','parser':'tesseract_grid','section':section,
            'text':text,'rows':[dataclasses.asdict(r) for r in rows],'tables':tables,
            'table_diagnostics':diags,'errors':errors,'rotation_clockwise':rotation,
            'deskew_counterclockwise':angle,'orientation_candidates':candidates,
            'ocr_image_size':[upright.shape[1],upright.shape[0]],'dpi':config.dpi}


REQUIRED_FIELDS = [
    'capital','fonds_propres','report_a_nouveau','resultat_net','total_immobilise','total_actif','total_passif',
    'dettes_financement','stocks','clients','fournisseurs','etat_debiteur','etat_crediteur',
    'comptes_associes_passif','banques_actif','banques_passif','chiffre_affaires','achats_rev_marchandises',
    'achats_consommes','autres_charges_externes','redevances_credit_bail','charges_personnel',
    'dotations_exploitation','resultat_exploitation','produits_financiers','charges_financieres',
    'resultat_financier','charges_non_courantes','resultat_non_courant','resultat_avant_impots','impots_resultats','caf',
]


def row_internal_consistency(row: FinancialRow, period: str) -> int:
    """Return +1 coherent, 0 unavailable, -1 contradicted by its own row arithmetic."""
    try:
        if period!='current': return 0
        if row.section=='bilan_actif':
            vals=[decimal_or_none(row.brut_current),decimal_or_none(row.amort_prov_current),decimal_or_none(row.current)]
            if all(v is not None for v in vals):
                return 1 if abs(vals[0]-vals[1]-vals[2])<=Decimal('.02') else -1
        if row.section=='cpc':
            vals=[decimal_or_none(row.operations_current),decimal_or_none(row.operations_prior_period),decimal_or_none(row.current)]
            if all(v is not None for v in vals):
                return 1 if abs(vals[0]+vals[1]-vals[2])<=Decimal('.02') else -1
    except Exception:
        pass
    return 0


def candidate_priority(row: FinancialRow, period: str, support: int = 1) -> tuple:
    preferred = FIELD_SECTION_PRIORITY.get(row.canonical_key or '', [])
    section = 100-preferred.index(row.section)*10 if row.section in preferred else 10
    n=normalize_label(row.label)
    total = n.startswith('total ')
    source = row.evidence.get(period,{})
    state = source.get('status','missing')
    usable = state in {'observed','explicit_zero'} and not source.get('repairs')
    consistency=row_internal_consistency(row,period)
    mapping=float(row.match_score or 0)
    conf=float(source.get('confidence') or 0)
    # Contradicted row arithmetic is a strong demotion. Repeated independent
    # observations and exact totals/section preference are strong positive cues.
    return (getattr(row,period) is not None, consistency>=0, support, consistency,
            total, section, usable, mapping, conf)

def resolve_canonical(rows: list[FinancialRow]) -> tuple[dict,dict,list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        if row.canonical_key:
            groups[row.canonical_key].append(row)
    canonical,candidates,conflicts = {},{},[]
    for key,items in sorted(groups.items()):
        # Use current-period support only to select the metadata-bearing base row.
        current_support=defaultdict(set)
        for r in items:
            if r.current is not None:
                current_support[Decimal(r.current)].add((r.page,r.table_id,r.section))
        best = max(items,key=lambda r:candidate_priority(r,'current',len(current_support.get(Decimal(r.current),set())) if r.current is not None else 0))
        entry = {name:getattr(best,name) for name in ['page','section','label','group_label','source_parser','confidence','mapping_method','match_score']}
        entry['period_status'] = {}
        entry['evidence'] = {}
        for period in VALUE_NAMES:
            eligible = [r for r in items if period in r.evidence]
            if not eligible:
                entry[period] = None
                entry['period_status'][period] = 'not_applicable'
                continue
            if key in {'tresorerie_actif','tresorerie_passif','total_actif_circulant','total_passif_circulant','total_immobilise','total_capitaux_permanents'}:
                totals=[r for r in eligible if normalize_label(r.label).startswith('total') and getattr(r,period) is not None]
                if totals:
                    eligible=totals
            support=defaultdict(set)
            for r in eligible:
                v=getattr(r,period)
                if v is not None:
                    support[Decimal(v)].add((r.page,r.table_id,r.section))
            ordered = sorted(eligible,key=lambda r:candidate_priority(r,period,len(support.get(Decimal(getattr(r,period)),set())) if getattr(r,period) is not None else 0),reverse=True)
            chosen = ordered[0]
            valued = [r for r in ordered if getattr(r,period) is not None]
            distinct = {Decimal(getattr(r,period)) for r in valued if r.evidence[period].get('value') is not None}
            entry[period] = getattr(chosen,period)
            state = chosen.evidence[period]['status']
            if len(distinct) > 1:
                conflict = {'key':key,'period':period,'values':sorted(format(v,'f') for v in distinct),
                            'candidates':[{'page':r.page,'section':r.section,'value':getattr(r,period),
                                           'label':r.label,'table_id':r.table_id,'row_index':r.row_index,
                                           'row_internal_consistency':row_internal_consistency(r,period)} for r in valued]}
                conflicts.append(conflict)
                # Keep the selected observation, but expose the conflict.  A candidate
                # corroborated by row arithmetic / independent sections may still be
                # promoted later by confidence_fusion.
                state = 'conflict'
            evidence = dict(chosen.evidence[period])
            evidence.update(page=chosen.page,section=chosen.section,label=chosen.label,
                            table_id=chosen.table_id,row_index=chosen.row_index,parser=chosen.source_parser,mapping_score=chosen.match_score,
                            row_internal_consistency=row_internal_consistency(chosen,period),
                            independent_support=len(support.get(Decimal(entry[period]),set())) if entry[period] is not None else 0)
            entry['evidence'][period] = evidence
            entry['period_status'][period] = state
        entry['usable_current'] = entry['period_status'].get('current') in {'observed','explicit_zero'} and not entry['evidence'].get('current',{}).get('repairs')
        entry['usable_previous'] = entry['period_status'].get('previous') in {'observed','explicit_zero'} and not entry['evidence'].get('previous',{}).get('repairs')
        canonical[key] = entry
        candidates[key] = [dataclasses.asdict(r) for r in items]
    return canonical,candidates,conflicts

def canonical_value(canonical: dict, key: str, period: str) -> Decimal | None:
    entry = canonical.get(key,{})
    if entry.get('confidence_fusion_version'):
        return decimal_or_none(entry.get('usable_'+period))
    if entry.get('validation_issues',{}).get(period):
        return None
    if entry.get('period_status',{}).get(period) not in {'observed','explicit_zero'}:
        return None
    if entry.get('evidence',{}).get(period,{}).get('repairs'):
        return None
    return decimal_or_none(entry.get(period))


def strict_sum(*values: Decimal | None) -> Decimal | None:
    if not values or any(v is None for v in values):
        return None
    return sum(values,Decimal(0))


def compute_derived(canonical: dict) -> dict:
    output = {}
    for period in ('current','previous'):
        def value(k):
            return canonical_value(canonical,k,period)
        metrics = {}
        def metric(name, keys, formula, function):
            inputs = {k:dec_str(value(k)) for k in keys}
            missing = [k for k,v in inputs.items() if v is None]
            result,status = None,'missing_or_unusable_input'
            if not missing:
                with localcontext() as context:
                    context.prec = 28
                    try:
                        result = function(*[value(k) for k in keys])
                        status = 'computed'
                    except (ZeroDivisionError,InvalidOperation):
                        status = 'zero_denominator'
            metrics[name] = {'value':dec_str(result),'status':status,'formula':formula,
                             'inputs':inputs,'missing_inputs':missing}
        metric('fonds_roulement',['total_capitaux_permanents','total_immobilise'],
               'total_capitaux_permanents - total_immobilise',lambda a,b:a-b)
        metric('bfr_total_hors_tresorerie',['total_actif_circulant','total_passif_circulant'],
               'total_actif_circulant - total_passif_circulant',lambda a,b:a-b)
        metric('tresorerie_nette',['tresorerie_actif','tresorerie_passif'],
               'tresorerie_actif - tresorerie_passif',lambda a,b:a-b)
        metric('tresorerie_nette_fdr_bfr',['total_capitaux_permanents','total_immobilise','total_actif_circulant','total_passif_circulant'],
               '(total_capitaux_permanents - total_immobilise) - (total_actif_circulant - total_passif_circulant)',lambda a,b,c,d:a-b-c+d)
        metric('achats_total',['achats_rev_marchandises','achats_consommes'],
               'achats_rev_marchandises + achats_consommes',lambda a,b:a+b)
        metric('ratio_autonomie_financiere',['fonds_propres','total_actif'],
               'fonds_propres / total_actif',lambda a,b:a/b)
        metric('rentabilite_commerciale',['resultat_net','chiffre_affaires'],
               'resultat_net / chiffre_affaires',lambda a,b:a/b)
        metric('rentabilite_financiere',['resultat_net','fonds_propres'],
               'resultat_net / fonds_propres',lambda a,b:a/b)
        # This is explicitly financing debt, not an inferred bank-loan amount.
        metric('dettes_financement_sur_fonds_propres',['dettes_financement','fonds_propres'],
               'dettes_financement / fonds_propres',lambda a,b:a/b)
        output[period] = metrics
    return output


def validate(canonical: dict, rows: list[FinancialRow], tolerance: Decimal = Decimal('.02')) -> list[dict]:
    checks = []
    equations = [
        ('total_actif_equals_total_passif', ['total_actif'], ['total_passif']),
        ('actif_components', ['total_actif'], ['total_immobilise','total_actif_circulant','tresorerie_actif']),
        ('passif_components', ['total_passif'], ['total_capitaux_permanents','total_passif_circulant','tresorerie_passif']),
        ('resultat_exploitation', ['produits_exploitation'], ['charges_exploitation','resultat_exploitation']),
        ('resultat_financier', ['produits_financiers'], ['charges_financieres','resultat_financier']),
        ('resultat_non_courant', ['produits_non_courants'], ['charges_non_courantes','resultat_non_courant']),
        ('resultat_avant_impots', ['resultat_avant_impots'], ['resultat_exploitation','resultat_financier','resultat_non_courant']),
        ('resultat_net', ['resultat_avant_impots'], ['impots_resultats','resultat_net']),
        ('chiffre_affaires', ['chiffre_affaires'], ['ventes_marchandises','ventes_biens_services']),
    ]
    def add_check(name,left,right,missing,**extra):
        difference = None if left is None or right is None else left-right
        status = 'not_evaluable' if difference is None else 'passed' if abs(difference) <= tolerance else 'failed'
        checks.append({'check':name,'status':status,'ok':None if status == 'not_evaluable' else status == 'passed',
                       'left':dec_str(left),'right':dec_str(right),'difference':dec_str(difference),
                       'tolerance':str(tolerance),'missing_inputs':missing,**extra})
    for period in ('current','previous'):
        for name,leftkeys,rightkeys in equations:
            missing = [k for k in leftkeys+rightkeys if canonical_value(canonical,k,period) is None]
            left = strict_sum(*[canonical_value(canonical,k,period) for k in leftkeys])
            right = strict_sum(*[canonical_value(canonical,k,period) for k in rightkeys])
            add_check(name+'_'+period,left,right,missing,period=period,involved_keys=leftkeys+rightkeys)
    for row in rows:
        if row.section not in {'bilan_actif','cpc'}:
            continue
        keys = ['brut_current','amort_prov_current','current'] if row.section == 'bilan_actif' else ['operations_current','operations_prior_period','current']
        values = [decimal_or_none(getattr(row,k)) if row.evidence.get(k,{}).get('status') in {'observed','explicit_zero'} else None for k in keys]
        if any(v is None for v in values):
            continue
        left = values[0]-values[1] if row.section == 'bilan_actif' else values[0]+values[1]
        add_check('row_net_equals_brut_minus_amort' if row.section == 'bilan_actif' else 'row_cpc_operations_sum',
                  left,values[2],[],page=row.page,table_id=row.table_id,row_index=row.row_index,label=row.label)
    return checks


def apply_validation_flags(canonical: dict, validations: list[dict]) -> None:
    for check in validations:
        if check['status'] != 'failed':
            continue
        for key,item in canonical.items():
            periods = []
            if key in check.get('involved_keys',[]):
                periods = [check['period']]
            elif 'page' in check:
                for period,evidence in item['evidence'].items():
                    if evidence.get('page')==check['page'] and evidence.get('table_id')==check['table_id'] and evidence.get('row_index')==check['row_index']:
                        periods.append(period)
            for period in periods:
                item.setdefault('validation_issues',{}).setdefault(period,[]).append(check['check'])
                if period in {'current','previous'}:
                    item['usable_'+period] = False


def rebuild_cached_rows(page: dict, config: Config) -> None:
    rows,diags = [],[]
    corrected = classify_page_structure(page.get('text',''))
    if corrected.startswith('annexe_') or corrected in {'detail_cpc','capital_repartition'}:
        page['section'] = corrected
    for table in page['tables']:
        section = corrected if corrected.startswith('annexe_') or corrected in {'detail_cpc','capital_repartition'} else table.get('section',page['section'])
        table['section'] = section
        if section in FINANCIAL_SECTIONS and not identify_schema(table['cells'],section)[0]:
            section = recover_section(table,page['parser'])
        rr,dd = rows_from_cells(table,section,page['page'],page['parser'],config.min_ocr_confidence)
        rows.extend(rr);diags.append(dd)
    page['rows'] = [dataclasses.asdict(r) for r in rows]
    page['table_diagnostics'] = diags


def source_units(pages: list[dict]) -> dict:
    candidates = []
    for page in pages:
        for pattern,unit,scale in [(r'\b(?:en\s+)?milliers\s+de\s+dirhams\b|\bKDH\b','KDH','1000'),
                                   (r'\b(?:en\s+)?millions\s+de\s+dirhams\b','millions_DH','1000000'),
                                   (r'\ben\s+dirhams\b|\bmontants?\s+en\s+DH\b','DH','1')]:
            match = re.search(pattern,page.get('text',''),re.I)
            if match:
                candidates.append({'page':page['page'],'unit':unit,'multiplier_to_DH':scale,'evidence':match[0]})
    return {'policy':'source_amounts_preserved_no_automatic_conversion','evidence':candidates,
            'unit':'not_stated' if not candidates else candidates[0]['unit'] if len({c['unit'] for c in candidates}) == 1 else 'mixed_or_ambiguous'}



def route_document_page(page, config):
    words=page.get_text('words')
    image_area=max((fitz.Rect(i['bbox']).get_area() for i in page.get_image_info()),default=0)
    hybrid=image_area>page.rect.get_area()*.55 and len(words)<60
    return 'scan' if config.ocr=='always' or (config.ocr!='never' and (len(words)<12 or hybrid)) else 'native'


def docling_tables(payload, page_number, scale, image_height):
    """Docling standard JSON -> the existing cell contract; spans are audited."""
    def bbox(b):
        if not b: return None
        l,t,r,bt=(float(b[k])*scale for k in ('l','t','r','b'))
        if b.get('coord_origin','TOPLEFT')=='BOTTOMLEFT': t,bt=image_height-t,image_height-bt
        return [min(l,r),min(t,bt),max(l,r),max(t,bt)]
    tables=[]
    for ti,item in enumerate(payload.get('tables',[])):
        data=item['data']; nr,nc=data['num_rows'],data['num_cols']
        matrix=[[{'text':'','bbox':None,'confidence':None,'missing_geometry':True} for _ in range(nc)] for _ in range(nr)]
        for cell in data.get('table_cells',[]):
            ri,ci=cell['start_row_offset_idx'],cell['start_col_offset_idx']
            if not (0<=ri<nr and 0<=ci<nc): continue
            matrix[ri][ci]={'text':cell.get('text',''),'bbox':bbox(cell.get('bbox')),'confidence':None,
                'missing_geometry':False,'span':[cell.get('end_row_offset_idx',ri+1),cell.get('end_col_offset_idx',ci+1)]}
            # Do not duplicate amounts into spanned cells.
        prov=item.get('prov',[])
        tables.append({'table_id':ti,'cells':matrix,'bbox':bbox(prov[0].get('bbox')) if prov else None,
                       'coordinate_space':'ocr_pixels_after_rotation_and_deskew','section':'generic'})
    return tables


def docling_scan_page(page, page_number, config):
    """Optional standard Docling pipeline; subprocess isolates timeout/model errors.
    No VLM pipeline is used. Only the routed scan page is submitted.
    """
    import cv2
    import numpy as np
    import importlib.util
    if importlib.util.find_spec('docling') is None: raise RuntimeError('docling_not_installed')
    pix=page.get_pixmap(dpi=config.dpi,colorspace=fitz.csGRAY,alpha=False)
    if pix.width*pix.height>60_000_000: raise ValueError('scan_pixel_budget_exceeded')
    image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width).copy()
    rotation,orientation_candidates=orientation(image,config)
    image,angle=deskew(rotate_image(image,rotation));h,w=image.shape
    with tempfile.TemporaryDirectory(prefix='financial_docling_') as temp:
        root=Path(temp); pdf=root/'page.pdf'; dest=root/'docling.json'
        ok,png=cv2.imencode('.png',image)
        if not ok: raise ValueError('png_encode_failed')
        with fitz.open() as one:
            p=one.new_page(width=w*72/config.dpi,height=h*72/config.dpi)
            p.insert_image(p.rect,stream=png.tobytes());one.save(pdf)
        # Pinned public standard API; handle the OcrMode transition explicitly.
        code='''import sys,json
from docling.document_converter import DocumentConverter,PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions,TesseractCliOcrOptions
opts=PdfPipelineOptions(do_ocr=True,do_table_structure=True)
try:
 from docling.datamodel.pipeline_options import OcrMode
 ocr=TesseractCliOcrOptions(mode=OcrMode.FULL_PAGE,lang=sys.argv[3].split('+'))
except ImportError:
 ocr=TesseractCliOcrOptions(force_full_page_ocr=True,lang=sys.argv[3].split('+'))
if hasattr(ocr,'tesseract_cmd'): ocr.tesseract_cmd=sys.argv[4]
opts.ocr_options=ocr
conv=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)})
doc=conv.convert(sys.argv[1]).document
payload=doc.export_to_dict();payload['_markdown']=doc.export_to_markdown()
with open(sys.argv[2],'w',encoding='utf8') as f: json.dump(payload,f,ensure_ascii=False)
'''
        proc=subprocess.run([sys.executable,'-c',code,str(pdf),str(dest),config.ocr_language,config.tesseract_cmd],
            capture_output=True,text=True,timeout=config.backend_timeout)
        if proc.returncode or not dest.exists(): raise RuntimeError('docling_conversion_failed:'+proc.stderr[-600:])
        payload=json.loads(dest.read_text(encoding='utf8'))
    text=payload.pop('_markdown','');section=detect_section(text)
    tables=docling_tables(payload,page_number,config.dpi/72,h);rows=[];diags=[]
    for table in tables:
        table['section']=section
        rr,dd=rows_from_cells(table,section,page_number,'docling',config.min_ocr_confidence)
        rows.extend(rr);diags.append(dd)
    if not tables: raise RuntimeError('docling_no_tables')
    return {'page':page_number,'kind':'scan','parser':'docling','section':section,'text':text,
        'rows':[dataclasses.asdict(r) for r in rows],'tables':tables,'table_diagnostics':diags,
        'errors':[],'rotation_clockwise':rotation,'deskew_counterclockwise':angle,
        'orientation_candidates':orientation_candidates,'ocr_image_size':[w,h],'dpi':config.dpi,
        'backend_raw':payload,'confidence_note':'Cell confidence unavailable; kept null, not fabricated.'}


def liteparse_fallback(page,page_number,config):
    """Preserve LiteParse spatial JSON as an auditable fallback.
    Flat text is never reinterpreted as trusted financial columns.
    """
    if not config.liteparse_cmd: return None
    with tempfile.TemporaryDirectory(prefix='financial_liteparse_') as temp:
        root=Path(temp);pdf=root/'page.pdf';dest=root/'liteparse.json'
        with fitz.open() as one:
            one.insert_pdf(page.parent,from_page=page.number,to_page=page.number);one.save(pdf)
        proc=subprocess.run([config.liteparse_cmd,'parse',str(pdf),'--format','json','-o',str(dest)],
            capture_output=True,text=True,timeout=config.backend_timeout)
        if proc.returncode or not dest.exists(): raise RuntimeError('liteparse_failed:'+proc.stderr[-500:])
        payload=json.loads(dest.read_text(encoding='utf8'))
    return {'page':page_number,'parser':'liteparse','payload':payload,'status':'raw_fallback_preserved'}


def scan_page(page,page_number,config):
    attempts=[]
    if config.scan_backend=='docling':
        try: return docling_scan_page(page,page_number,config)
        except Exception as exc: attempts.append({'parser':'docling','status':'failed','error':str(exc)[:700]})
        # LiteParse is invoked only after the selected primary parser fails.
        fallback=None
        if config.liteparse_cmd:
            try: fallback=liteparse_fallback(page,page_number,config)
            except Exception as exc: attempts.append({'parser':'liteparse','status':'failed','error':str(exc)[:700]})
        record=scan_page_tesseract(page,page_number,config)
        if fallback: record['liteparse_fallback']=fallback
        record['backend_attempts']=attempts
        return record
    record=scan_page_tesseract(page,page_number,config)
    if record.get('errors') and config.liteparse_cmd:
        try: record['liteparse_fallback']=liteparse_fallback(page,page_number,config)
        except Exception as exc: record.setdefault('backend_attempts',[]).append({'parser':'liteparse','status':'failed','error':str(exc)[:700]})
    return record


def page_worker(pdf_path: str, page_index: int, config_dict: dict, cache_path: str, cache_key: str) -> dict:
    config = Config(**config_dict)
    path = Path(cache_path)
    if config.cache and path.exists():
        try:
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached.get('cache_key') == cache_key and not cached['result'].get('errors'):
                rebuild_cached_rows(cached['result'],config)
                cached['result']['cache_hit'] = True
                return cached['result']
        except (ValueError,KeyError,OSError):
            pass
    started = time.monotonic()
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_index]
            native_words = page.get_text('words')
            # Native tables are used when the page has a real text layer. A
            # large background image with only a footer is routed to OCR.
            image_area = max((fitz.Rect(i['bbox']).get_area() for i in page.get_image_info()),default=0)
            hybrid = image_area > page.rect.get_area()*.55 and len(native_words) < 60
            use_ocr = route_document_page(page,config)=='scan'
            if use_ocr:
                result = scan_page(page,page_index+1,config)
            else:
                result = native_page(page,page_index+1,config)
                if len(native_words)<12:
                    result['errors'].append('scanned_page_ocr_disabled')
                # Targeted fallback only for an identified financial page
                # whose native table structure is missing.
                if config.ocr != 'never' and result['section'] in FINANCIAL_SECTIONS and not result['rows']:
                    result = scan_page(page,page_index+1,config)
        result['elapsed_seconds'] = round(time.monotonic()-started,3)
        result['cache_hit'] = False
    except Exception as exc:
        result = {'page':page_index+1,'kind':'error','parser':None,'section':'unknown',
                  'text':'','rows':[],'tables':[],'table_diagnostics':[],
                  'errors':[type(exc).__name__+': '+str(exc)[:1000]],'elapsed_seconds':round(time.monotonic()-started,3)}
    if config.cache:
        save_json(path,{'cache_key':cache_key,'result':result})
    return result


def safe_stem(path: Path, digest: str) -> str:
    stem = re.sub(r'[^A-Za-z0-9_.-]+','_',strip_accents(path.stem)).strip('_.')[:80] or 'document'
    return stem+'_'+digest[:10]


def spreadsheet_safe(value: Any) -> Any:
    # Preserve numerical minus signs; escape formulas in source labels only.
    if isinstance(value,str) and value.startswith(('=','+','@','-')) and normalize_amount(value) is None:
        return "'"+value
    return value


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:spreadsheet_safe(json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),(list,dict)) else row.get(k)) for k in fields})


def write_outputs(out_dir: Path, result: dict, pages: list[dict]) -> None:
    out_dir.mkdir(parents=True,exist_ok=True)
    save_json(out_dir/'extraction.json',result)
    diagnostics = {k:result[k] for k in ['quality','validations','conflicts','missing_required_fields','present_but_blank_fields']}
    diagnostics['targeted_repairs'] = result.get('targeted_repairs',[])
    diagnostics['llm_audit'] = result.get('llm_audit',{})
    diagnostics['pages'] = [{k:v for k,v in page.items() if k not in {'text','rows','tables'}} for page in pages]
    save_json(out_dir/'diagnostics.json',diagnostics)
    canonical_rows = [{'key':key,**value} for key,value in result['canonical'].items()]
    fields = ['key',*VALUE_NAMES,'page','section','label','source_parser','confidence','usable_current','usable_previous','period_status','status','value_status','value_diagnostics','quality_flags','computed_candidates','confidence_components','evidence']
    write_csv(out_dir/'canonical_fields.csv',canonical_rows,fields)
    write_csv(out_dir/'all_rows.csv',result['all_rows'],[f.name for f in dataclasses.fields(FinancialRow)]+['row_kind','cells'])
    markdown = []
    for page in pages:
        markdown.append(f"## Page {page['page']} — {page['section']} — {page['parser']}\n\n"+page.get('text',''))
        for table in page['tables']:
            matrix = table['cells']
            if not matrix:
                continue
            def escape(text):
                return compact_text(text).replace('|','\\|')
            lines = ['| '+' | '.join(escape(c['text']) for c in matrix[0])+' |',
                     '| '+' | '.join('---' for _ in matrix[0])+' |']
            lines += ['| '+' | '.join(escape(c['text']) for c in row)+' |' for row in matrix[1:]]
            markdown.append('\n'.join(lines))
        save_json(out_dir/'raw'/f"page_{page['page']:03d}_cells.json",{k:v for k,v in page.items() if k not in {'rows'}})
    (out_dir/'selected.md').write_text('\n\n'.join(markdown),encoding='utf-8')


# Incremental business/audit layer. The native table and identity extractors above
# are deliberately retained; money is never inferred into the extraction layer.

def cell_proof(page, table, ri, ci, numeric=True):
    cell = table['cells'][ri][ci]
    raw = cell.get('text', '')
    parsed = (parse_amount_ocr_relaxed(raw) if page['parser'] != 'pymupdf' else parse_amount(raw)) if numeric else {
        'value': raw.strip() or None, 'raw': raw, 'status': 'observed' if raw.strip() else 'blank', 'repairs': []}
    if cell.get('missing_geometry'):
        parsed.update(value=None, status='missing_cell')
    parsed.update(value_kind='amount' if numeric else 'text',page=page['page'], table_id=table['table_id'], row_index=ri,
                  column_index=ci, bbox=cell.get('bbox'), parser=page['parser'],
                  coordinate_space=table.get('coordinate_space'), schema_method=table.get('capital_schema_method'),
                  confidence=cell.get('confidence'), ocr_attempts=cell.get('ocr_attempts', []))
    return parsed


def document_rows(pages, financial_rows):
    """Every physical table row and non-table text line, plus semantic rows.

    Physical and semantic views share locators; repetitions are not independent
    observations. Text lines are retained as a separate view, never mapped twice.
    """
    rows = [dict(r, row_kind='financial') for r in financial_rows]
    for page in pages:
        for table in page.get('tables', []):
            for ri, cells in enumerate(table['cells']):
                rows.append({'row_kind': 'physical_table', 'page': page['page'],
                    'section': table.get('section', page['section']), 'table_id': table['table_id'],
                    'row_index': ri, 'source_parser': page['parser'],
                    'raw': ' | '.join(c.get('text','') for c in cells),
                    'cells': [cell_proof(page, table, ri, ci, False) for ci in range(len(cells))]})
        for ri, line in enumerate(page.get('text','').splitlines()):
            rows.append({'row_kind':'text_line', 'page':page['page'], 'section':page['section'],
                'table_id':None, 'row_index':ri, 'raw':line, 'source_parser':page['parser'], 'bbox':None})
    return rows


def business_put(obj, key, proof):
    """Keep every observation and explicitly flag differing printed values."""
    ev = obj.setdefault('evidence', {}).setdefault(key, [])
    ev.append(proof)
    values = {str(x['value']) for x in ev if x['value'] is not None}
    obj[key] = next(iter(values)) if len(values) == 1 else None
    if len(values) > 1:
        obj.setdefault('quality_flags', []).append('conflicting_observations:' + key)


def parse_resultat_fiscal(pages):
    result = {k:None for k in ('resultat_net_comptable','resultat_brut_fiscal','resultat_net_fiscal','deficit_net_fiscal')}
    result.update(reintegrations_fiscales={'total':None,'details':[]},
                  deductions_fiscales={'total':None,'details':[]}, evidence={}, quality_flags=[])
    for page in pages:
        if 'resultat net comptable au resultat net fiscal' not in normalize_label(page.get('text','')) and page['section'] != 'resultat_fiscal':
            continue
        section = None
        for table in page.get('tables', []):
            header = next((i for i,r in enumerate(table['cells']) if sum('montant' in normalize_label(c['text']) for c in r)>=1), None)
            if header is None:
                continue
            head = table['cells'][header]
            amount_cols=[i for i,c in enumerate(head) if 'montant' in normalize_label(c['text'])]
            plus = next((i for i,c in enumerate(head) if 'montant' in normalize_label(c['text']) and '+' in c['text']), None)
            minus = next((i for i,c in enumerate(head) if 'montant' in normalize_label(c['text']) and any(x in c['text'] for x in ('-','—','–','−'))), None)
            if (plus is None or minus is None) and len(amount_cols)>=2:
                plus,minus=amount_cols[0],amount_cols[1]
                result['quality_flags'].append('fiscal_plus_minus_columns_inferred_from_DGI_order')
            if plus is None or minus is None or plus==minus:
                result['quality_flags'].append('unresolved_fiscal_columns'); continue
            for ri in range(header+1, len(table['cells'])):
                cells = table['cells'][ri]
                labels = [c['text'].strip() for c in cells[:min(plus,minus)] if c['text'].strip()]
                label = labels[-1] if labels else ''
                n = normalize_label(' '.join(labels))
                if not n: continue
                if 'reintegrations fiscal' in n: section='reintegrations_fiscales'
                elif 'deductions fiscal' in n: section='deductions_fiscales'
                elif any(t in n for t in ('resultat brut fiscal','reports deficitaires','resultat net fiscal','cumul des amortissements')): section=None
                proofs = [cell_proof(page,table,ri,ci) for ci in range(min(plus,minus),len(cells))]
                printed = [p for p in proofs if p['value'] is not None]
                if n in ('total','total total'):
                    result.setdefault('printed_column_totals',[]).append({'page':page['page'],
                        'plus':cell_proof(page,table,ri,plus),'minus':cell_proof(page,table,ri,minus),
                        'status':'column_totals_not_automatically_gross_result'})
                target = None; sign = 1
                if 'deficit net fiscal' in n:
                    target='deficit_net_fiscal'; sign=-1
                elif 'benefice net fiscal' in n:
                    target='resultat_net_fiscal'
                elif 'resultat net comptable' in n or (('benefice net' in n or 'perte nette' in n) and 'fiscal' not in n and section is None):
                    target='resultat_net_comptable'; sign=-1 if 'perte' in n else 1
                elif 'benefice brut' in n or 'deficit brut fiscal' in n:
                    target='resultat_brut_fiscal'; sign=-1 if 'deficit' in n else 1
                if target:
                    # Gross fiscal amount is often printed in T1/T2 rather than +/-.
                    for proof in printed:
                        if sign < 0:
                            proof=dict(proof, value=dec_str(-Decimal(proof['value'])), sign_rule='printed_loss_or_deficit_label')
                        business_put(result,target,proof)
                    if not printed and target not in result['evidence']:
                        result['evidence'][target]=proofs
                elif section and label:
                    clean = normalize_label(label)
                    if clean.startswith(('reintegrations fiscal','deductions fiscal')):
                        ci = plus if section=='reintegrations_fiscales' else minus
                        business_put(result[section],'total',cell_proof(page,table,ri,ci))
                    elif clean != 'total' and not clean.startswith(('total ', 'ii ', 'iii ')):
                        ci=plus if section=='reintegrations_fiscales' else minus
                        proof=cell_proof(page,table,ri,ci)
                        if proof['value'] is not None:
                            result[section]['details'].append({'label':label,'amount':proof['value'],'evidence':proof})

    # Conservative decimal-separator recovery for a printed total: only when the
    # digits exactly match the sum of all parsed details after removing punctuation.
    for block in ('reintegrations_fiscales','deductions_fiscales'):
        data=result[block]
        if data['details']:
            detail_sum=sum((Decimal(x['amount']) for x in data['details'] if x.get('amount') is not None),Decimal(0))
            total=decimal_or_none(data.get('total'))
            if total is not None and total!=detail_sum:
                raw_ev=(data.get('evidence',{}).get('total') or [])
                raw=' '.join(str(e.get('raw','')) for e in raw_ev)
                digits=re.sub(r'\D','',raw)
                target_digits=re.sub(r'\D','',format(detail_sum,'.2f'))
                if digits and digits==target_digits:
                    data['printed_total_original']=data['total']
                    data['total']=dec_str(detail_sum)
                    data.setdefault('quality_flags',[]).append('decimal_separator_recovered_from_detail_sum')
                    result['quality_flags'].append(block+':decimal_separator_recovered_from_detail_sum')
    return result


CAPITAL_FIELDS = ('nom_prenom','raison_sociale','if','cni','carte_etranger','adresse',
                  'titres_previous','titres_current','valeur_nominale','capital_souscrit','capital_appele','capital_libere')

def capital_header(text):
    n=normalize_label(text)
    if 'nom' in n and 'prenom' in n: return 'nom_prenom'
    if 'raison sociale' in n: return 'raison_sociale'
    if re.search(r'\bif\b',n): return 'if'
    if re.search(r'\b(?:cni|cnt)\b',n): return 'cni'
    if 'carte' in n and 'etranger' in n: return 'carte_etranger'
    if 'adresse' in n: return 'adresse'
    if 'titres' in n: return 'titres_previous' if 'precedent' in n else 'titres_current' if 'actuel' in n else None
    if 'valeur nomin' in n or ('valeur' in n and ('action' in n or 'part sociale' in n)): return 'valeur_nominale'
    for word,field in [('souscrit','capital_souscrit'),('appele','capital_appele'),('libere','capital_libere')]:
        if word in n or (field=='capital_souscrit' and 'capital' in n and re.search(r'\b10$',n)): return field
    return None


def associate_identity(person):
    # Exact identity only; no ordinal or fuzzy cross-table joins.
    return tuple(normalize_label(re.sub(r'^\s*\d+\s*[-.]\s*','',person.get(k) or '')) for k in ('nom_prenom','raison_sociale'))



def capital_ordinal(person: dict) -> int | None:
    if person.get('_source_ordinal') is not None:
        return person['_source_ordinal']
    for key in ('nom_prenom','raison_sociale'):
        raw=person.get(key) or ''
        m=re.match(r'^\s*(\d{1,2})\s*[-.) ]?',raw)
        if m:
            try:return int(m.group(1))
            except ValueError:pass
    return None


def capital_name_similarity(a: dict, b: dict) -> float:
    aa=' '.join(x for x in associate_identity(a) if x)
    bb=' '.join(x for x in associate_identity(b) if x)
    return SequenceMatcher(None,aa,bb).ratio() if aa and bb else 0.0

def parse_capital_repartition(pages):
    result={'capital_social':None,'associes':[], 'evidence':{},'quality_flags':[]}
    for page in pages:
        if classify_page_structure(page.get('text',''))!='capital_repartition': continue
        for line_index,line in enumerate(page.get('text','').splitlines()):
            match=re.search(r'capital social ou personnel\s*:?\s*([0-9][0-9 .,]*)',line,re.I)
            if match:
                parsed=parse_amount(match[1],ocr=page['parser']!='pymupdf')
                if parsed['value'] is not None:
                    parsed.update(raw=line,amount_raw=match[1],page=page['page'],table_id=None,
                        row_index=line_index,column_index=None,bbox=None,coordinate_space=None,
                        parser=page['parser'],confidence=100. if page['parser']=='pymupdf' else None,
                        value_kind='amount',source_view='text_line')
                    business_put(result,'capital_social',parsed)
        for table in page.get('tables',[]):
            matrix=table['cells']
            for ri,cells in enumerate(matrix):
                for ci,cell in enumerate(cells):
                    match=re.search(r'capital social ou personnel\s*:\s*(.+)',cell['text'],re.I)
                    if match:
                        proof=cell_proof(page,table,ri,ci,False)
                        parsed=parse_amount(match[1],ocr=page['parser']!='pymupdf')
                        proof.update(value=parsed['value'],status=parsed['status'],amount_raw=match[1])
                        business_put(result,'capital_social',proof)
            hi=next((i for i,r in enumerate(matrix) if sum(capital_header(c['text']) is not None for c in r)>=3),None)
            if hi is None: continue
            starts=[(ci,capital_header(c['text'])) for ci,c in enumerate(matrix[hi]) if capital_header(c['text'])]
            if page['parser']!='pymupdf' and len(matrix[hi])==11:
                expected=dict(enumerate(CAPITAL_FIELDS[:6]+('titres_previous','titres_current','valeur_nominale','capital_souscrit'),start=1))
                anchors=sum(expected.get(ci)==key for ci,key in starts)
                if anchors>=3:
                    starts=list(expected.items())
                    table['capital_schema_method']='DGI_11_columns_with_'+str(anchors)+'_aligned_header_anchors'
            for ri in range(hi+1,len(matrix)):
                person={k:None for k in CAPITAL_FIELDS}; person['evidence']={}; person['quality_flags']=[]
                for ix,(ci,key) in enumerate(starts):
                    end=min(starts[ix+1][0] if ix+1<len(starts) else len(matrix[ri]), next((j for j in range(ci+1,len(matrix[hi])) if matrix[hi][j]['text'].strip()),len(matrix[ri])))
                    eligible=[j for j in range(ci,min(end,len(matrix[ri]))) if matrix[ri][j]['text'].strip()
                              and 'repartition du capital' not in normalize_label(matrix[ri][j]['text'])]
                    if not eligible:
                        if ci < len(matrix[ri]): business_put(person,key,cell_proof(page,table,ri,ci,key in CAPITAL_FIELDS[6:]))
                        continue
                    numeric=key in CAPITAL_FIELDS[6:]
                    for j in eligible:
                        proof=cell_proof(page,table,ri,j,numeric)
                        if not numeric and key in ('nom_prenom','raison_sociale'):
                            raw_name=proof.get('value') or ''
                            ordinal=re.match(r'^\s*(\d{1,2})\s*[-.) ]?',raw_name)
                            if ordinal and person.get('_source_ordinal') is None:
                                person['_source_ordinal']=int(ordinal.group(1))
                            proof['value']=re.sub(r'^\s*\d+\s*[-.) ]?\s*','',raw_name).strip() or None
                        if key=='if' and proof['value'] is not None and not re.fullmatch(r'\d{1,15}',proof['value']):
                            proof.update(value=None,status='invalid_identifier')
                            person['quality_flags'].append('invalid_if_text')
                        business_put(person,key,proof)
                enrich_identity_identifiers(person)
                identity=associate_identity(person)
                if not any(identity): continue
                matches=[p for p in result['associes'] if associate_identity(p)==identity]
                # Continuation tables often OCR the same shareholder name slightly
                # differently.  Merge only when an explicit ordinal agrees and the
                # normalized names remain reasonably similar; otherwise keep an audit fragment.
                if not matches:
                    ord_person=capital_ordinal(person)
                    ordinal_matches=[p for p in result['associes'] if ord_person is not None and capital_ordinal(p)==ord_person and capital_name_similarity(p,person)>=.55]
                    if len(ordinal_matches)==1:
                        matches=ordinal_matches
                        person['quality_flags'].append('controlled_ordinal_name_join')
                if len(matches)==1 and not any(e['page']==page['page'] and e['table_id']==table['table_id'] for ev in matches[0]['evidence'].values() for e in ev):
                    existing=matches[0]
                    controlled='controlled_ordinal_name_join' in person['quality_flags']
                    for key,proofs in person['evidence'].items():
                        if controlled and key in ('nom_prenom','raison_sociale'):
                            continue
                        for proof in proofs: business_put(existing,key,proof)
                    if controlled:
                        existing['quality_flags'].append('controlled_ordinal_name_join')
                else:
                    if matches: person['quality_flags'].append('ambiguous_duplicate_identity')
                    has_primary=any(field in {k for _,k in starts} for field in ('capital_souscrit','titres_current','cni','if'))
                    if not has_primary:
                        person['quality_flags'].append('unmatched_continuation_identity')
                        result.setdefault('unmatched_fragments',[]).append(person)
                    else: result['associes'].append(person)
    return result


def accounting_validation(canonical, rows, fiscal):
    """Equations test observations, including uncertain OCR, not usable values.
    A failure detects a contradiction; it does not identify which operand is wrong.
    """
    checks=[]
    def check(name, operands, terms, **meta):
        missing=[k for k,v in operands.items() if v is None]
        difference=None if missing else sum((Decimal(operands[k])*Decimal(str(s)) for k,s in terms.items()),Decimal(0))
        status='not_evaluable' if missing else 'passed' if abs(difference)<=Decimal('.02') else 'failed'
        checks.append(dict(check=name,status=status,ok=None if missing else status=='passed',
            inputs=operands,coefficients=terms,difference=dec_str(difference),tolerance='0.02',missing_inputs=missing,**meta))
    equations=[('total_actif_equals_total_passif',{'total_actif':1,'total_passif':-1}),
        ('actif_components',{'total_actif':1,'total_immobilise':-1,'total_actif_circulant':-1,'tresorerie_actif':-1}),
        ('passif_components',{'total_passif':1,'total_capitaux_permanents':-1,'total_passif_circulant':-1,'tresorerie_passif':-1}),
        ('resultat_exploitation',{'produits_exploitation':1,'charges_exploitation':-1,'resultat_exploitation':-1}),
        ('resultat_financier',{'produits_financiers':1,'charges_financieres':-1,'resultat_financier':-1}),
        ('resultat_courant',{'resultat_exploitation':1,'resultat_financier':1,'resultat_courant':-1}),
        ('resultat_non_courant',{'produits_non_courants':1,'charges_non_courantes':-1,'resultat_non_courant':-1}),
        ('resultat_avant_impots',{'resultat_courant':1,'resultat_non_courant':1,'resultat_avant_impots':-1}),
        ('resultat_net',{'resultat_avant_impots':1,'impots_resultats':-1,'resultat_net':-1}),
        ('chiffre_affaires',{'chiffre_affaires':1,'ventes_marchandises':-1,'ventes_biens_services':-1})]
    for period in ('current','previous'):
        for name,terms in equations:
            check(name+'_'+period,{k:canonical.get(k,{}).get(period) for k in terms},terms,period=period,involved_keys=list(terms))
    for row in rows:
        if row['section'] not in {'bilan_actif','cpc'}: continue
        terms={'brut_current':1,'amort_prov_current':-1,'current':-1} if row['section']=='bilan_actif' else {'operations_current':1,'operations_prior_period':1,'current':-1}
        if not any(row.get(k) is not None for k in terms): continue
        check('row_net_equals_brut_minus_amort' if row['section']=='bilan_actif' else 'row_cpc_operations_sum',
              {k:row.get(k) for k in terms},terms,page=row['page'],table_id=row['table_id'],row_index=row['row_index'],period='current',row_terms=True)
    for block in ('reintegrations_fiscales','deductions_fiscales'):
        data=fiscal[block]; terms={'total':1,**{f'detail_{i}':-1 for i in range(len(data['details']))}}
        operands={'total':data['total'],**{f'detail_{i}':v['amount'] for i,v in enumerate(data['details'])}}
        if not data['details']: operands['details_absent']=None;terms['details_absent']=-1
        check('fiscal_'+block,operands,terms,business_section='resultat_fiscal')
    check('fiscal_resultat_brut',{'net_comptable':fiscal['resultat_net_comptable'],'reintegrations':fiscal['reintegrations_fiscales']['total'],
          'deductions':fiscal['deductions_fiscales']['total'],'brut':fiscal['resultat_brut_fiscal']},
          {'net_comptable':1,'reintegrations':1,'deductions':-1,'brut':-1},business_section='resultat_fiscal')
    # Complete CAF formula: absent printed components remain unknown.
    caf_specs=[('dotations_exploitation',1),('dotations_financieres',1),('dotations_non_courantes',1),
        ('reprises_exploitation',-1),('reprises_financieres',-1),('reprises_non_courantes',-1),
        ('produits_cessions',-1),('valeurs_nettes',1)]
    for period in ('current','previous'):
        inputs={'resultat_net':canonical.get('resultat_net',{}).get(period),'caf':canonical.get('caf',{}).get(period)}
        terms={'resultat_net':1,'caf':-1}
        for key,sign in caf_specs:
            words=key.split('_')
            found=[r.get(period) for r in rows if r['section']=='esg' and all(w in normalize_label(r['label']) for w in words)
                   and ('(+)' in r['label'] or '(-)' in r['label'] or 'autofinancement' in normalize_label(r.get('group_label','')))]
            vals=set(v for v in found if v is not None)
            inputs[key]=next(iter(vals)) if len(vals)==1 else None;terms[key]=sign
        check('caf_esg_complete_'+period,inputs,terms,period=period,involved_keys=['caf','resultat_net'])
    return checks


def inter_section_checks(candidates):
    """Compare equal semantic fields and periods, retaining every occurrence."""
    checks=[]
    for key,rows in candidates.items():
        for period in ('current','previous'):
            observed=[r for r in rows if r.get(period) is not None]
            sections={r['section'] for r in observed}
            if len(sections)<2: continue
            vals={Decimal(r[period]) for r in observed}
            checks.append({'check':'inter_section_'+key+'_'+period,
                'status':'passed' if len(vals)==1 else 'failed', 'ok':len(vals)==1,
                'period':period,'involved_keys':[key], 'coefficients':{},
                'difference':dec_str(max(vals)-min(vals)),
                'occurrences':[{'page':r['page'],'table_id':r.get('table_id'),'row_index':r.get('row_index'),
                    'section':r['section'],'label':r['label'],'value':r[period],
                    'evidence':r.get('evidence',{}).get(period,{})} for r in observed],
                'interpretation':'source_or_transcription_divergence' if len(vals)>1 else 'matching_independent_sections'})
    return checks


def equity_component_checks(rows):
    checks=[];groups=defaultdict(list)
    for r in rows:
        if r['section']=='bilan_passif':groups[(r['page'],r['table_id'])].append(r)
    def disclosure(label):
        n=normalize_label(label)
        # "capital appelé" and "dont versé" are disclosures of paid-up capital,
        # not additional components of equity.  OCR variants such as appclé/appcle
        # are handled by the root pattern.
        if 'dont verse' in n: return True
        if n.startswith('moins') and 'capital' in n and re.search(r'app[a-z0-9]{1,6}',n) and 'non appele' not in n:
            return True
        return False
    for (page,table),items in groups.items():
        items.sort(key=lambda r:r['row_index'])
        starts=[i for i,r in enumerate(items) if r.get('canonical_key')=='capital']
        ends=[i for i,r in enumerate(items) if r.get('canonical_key')=='fonds_propres']
        if not starts or not ends or starts[0]>=ends[0]:continue
        block=[r for r in items[starts[0]:ends[0]] if not disclosure(r['label'])]
        total=items[ends[0]]
        expected=('reserve legale','autres reserves','report a nouveau','resultat net','prime','evaluation')
        complete=all(any(t in normalize_label(r['label']) for r in block) for t in expected)
        for period in ('current','previous'):
            printed=[r for r in block if r.get(period) is not None]
            operands={str(r['row_index']):r[period] for r in printed}
            terms={str(r['row_index']):(-1 if ('non appele' in normalize_label(r['label']) and normalize_label(r['label']).startswith('moins')) else 1) for r in printed}
            diff=None
            if complete and total.get(period) is not None:
                diff=sum((Decimal(v)*terms[k] for k,v in operands.items()),Decimal(0))-Decimal(total[period])
            checks.append({'check':'equity_visible_components_'+period,'status':'not_evaluable' if diff is None else 'passed' if abs(diff)<=Decimal('.02') else 'failed',
                'ok':None if diff is None else abs(diff)<=Decimal('.02'), 'period':period,
                'page':page,'table_id':table,'involved_keys':['fonds_propres'], 'coefficients':{},
                'difference':dec_str(diff),'printed_total':total.get(period),'inputs':operands,
                'business_rule':'complete_equity_block_blank_components_treated_as_zero_for_this_check_only',
                'excluded_disclosure_rows':[r['row_index'] for r in items[starts[0]:ends[0]] if disclosure(r['label'])],
                'blank_rows':[r['row_index'] for r in block if r.get(period) is None],
                'extraction_values_modified':False})
    return checks


def apply_two_constraint_reconstructions(result: dict) -> list[dict]:
    """Resolve an OCR-corrupted aggregate only when TWO independent constraints agree.

    The original OCR observation is preserved under ``observed_<period>`` and in
    evidence.  A reconstruction requires (a) the printed row arithmetic and
    (b) a separate business equation to yield the same amount within 0.02 DH.
    Native PDF values are never reconstructed here.
    """
    allowed={'produits_non_courants','charges_non_courantes','resultat_exploitation',
             'resultat_financier','resultat_courant','resultat_avant_impots',
             'total_actif','total_passif','total_actif_circulant','total_passif_circulant'}
    changes=[]
    checks=result.get('validations',[])
    for key,entry in result.get('canonical',{}).items():
        if key not in allowed: continue
        for period in ('current','previous'):
            observed=entry.get(period)
            proof=entry.get('evidence',{}).get(period,{})
            if observed is None or proof.get('parser')=='pymupdf': continue
            # Only repair uncertain OCR observations. High-confidence coherent values
            # are left untouched even if another equation elsewhere fails.
            conf=float(proof.get('confidence') or 0)
            if conf>=85 and entry.get('period_status',{}).get(period) not in {'low_confidence','conflict','unparsed'}:
                continue
            row_candidates=[]; equation_candidates=[]
            for c in checks:
                if c.get('status')!='failed' or c.get('period')!=period:
                    continue
                if c.get('row_terms'):
                    if not all(proof.get(k)==c.get(k) for k in ('page','table_id','row_index')):
                        continue
                    coeff=c.get('coefficients',{}).get(period)
                    if coeff and c.get('difference') is not None:
                        cand=Decimal(observed)-Decimal(c['difference'])/Decimal(str(coeff))
                        row_candidates.append((cand,c['check']))
                elif key in c.get('coefficients',{}) and c.get('difference') is not None:
                    coeff=c['coefficients'][key]
                    if coeff:
                        cand=Decimal(observed)-Decimal(c['difference'])/Decimal(str(coeff))
                        equation_candidates.append((cand,c['check']))
            match=None
            for a,ac in row_candidates:
                for b,bc in equation_candidates:
                    if ac==bc: continue
                    if abs(a-b)<=Decimal('.02'):
                        match=((a+b)/2,ac,bc);break
                if match:break
            if not match: continue
            candidate, row_check, business_check=match
            if abs(candidate-Decimal(observed))<=Decimal('.02'):
                continue
            entry['observed_'+period]=observed
            entry[period]=dec_str(candidate)
            entry.setdefault('resolution',{})[period]={
                'status':'reconstructed_cross_checked','value':dec_str(candidate),
                'original_observation':observed,'row_constraint':row_check,
                'business_constraint':business_check,
                'original_evidence':dict(proof),'source_values_overwritten':False}
            entry['period_status'][period]='reconstructed_cross_checked'
            proof['resolution_status']='reconstructed_cross_checked'
            proof['resolved_value']=dec_str(candidate)
            changes.append({'key':key,'period':period,'before':observed,'after':dec_str(candidate),
                            'row_constraint':row_check,'business_constraint':business_check})
    result['cross_checked_reconstructions']=changes
    return changes

def confidence_fusion(result):
    checks=result['validations']; candidates=result['canonical_candidates']
    for key,entry in result['canonical'].items():
        entry['quality_flags']=[]; entry['value_status']={};entry['confidence_components']={}
        entry['computed_candidates']={};entry['value_diagnostics']={};entry.pop('validation_issues',None)
        for period in VALUE_NAMES:
            proof=entry.get('evidence',{}).get(period,{})
            value=entry.get(period)
            reconstructed=entry.get('period_status',{}).get(period)=='reconstructed_cross_checked'
            same=[]; conflicting=[]
            for row in candidates.get(key,[]):
                ev=row.get('evidence',{}).get(period,{})
                obs=row.get(period)
                if key in {'tresorerie_actif','tresorerie_passif'} and normalize_label(proof.get('label','')).startswith('total') and not normalize_label(row.get('label','')).startswith('total') and obs != value:
                    continue
                locator=(row['page'],row['table_id'])
                if obs is not None:
                    if reconstructed:
                        # Raw observations remain in audit but do not invalidate a value
                        # reconstructed by two independent accounting constraints.
                        if value is not None and Decimal(obs)==Decimal(value): same.append((locator,row,ev))
                    else:
                        (same if value is not None and Decimal(obs)==Decimal(value) else conflicting).append((locator,row,ev))
            independent=len({loc for loc,_,_ in same})
            parsers=len({r['source_parser'] for _,r,_ in same})
            primary_check_name=f'{key}_{period}'
            primary_pass=any(c.get('check')==primary_check_name and c.get('status')=='passed' for c in checks)
            inter_pass=[c for c in checks if c.get('check')=='inter_section_'+key+'_'+period and c.get('status')=='passed']
            if inter_pass:
                independent=max(independent,len({(o.get('page'),o.get('table_id'),o.get('section')) for c in inter_pass for o in c.get('occurrences',[])}))
            failures=[]; passed=[]
            for c in checks:
                relevant=key in c.get('involved_keys',[]) and c.get('period')==period
                if c.get('row_terms'):
                    relevant=all(proof.get(k)==c.get(k) for k in ('page','table_id','row_index')) and period in c['coefficients']
                if not relevant: continue
                if c['status']=='failed':
                    # Do not blame a value that already satisfies its own primary
                    # accounting equation for a downstream equation failure. Example:
                    # a correct RESULTAT COURANT must not become suspect only because
                    # RESULTAT AVANT IMPOTS was OCR-corrupted.
                    downstream = (not c.get('row_terms') and c.get('check')!=primary_check_name)
                    if primary_pass and downstream:
                        continue
                    failures.append(c['check'])
                    operand=period if c.get('row_terms') else key
                    coeff=c['coefficients'].get(operand)
                    if coeff and value is not None:
                        candidate=Decimal(value)-Decimal(c['difference'])/Decimal(str(coeff))
                        entry['computed_candidates'].setdefault(period,[]).append({'value':dec_str(candidate),'check':c['check'],
                            'status':'hypothesis_requires_targeted_verification','assumption':'all_other_operands_correct'})
                elif c['status']=='passed': passed.append(c['check'])
            ocr=proof.get('confidence'); ocr=0.5 if ocr is None else min(1.,max(0.,float(ocr)/100))
            mapping=min(1.,float(proof.get('mapping_score',entry.get('match_score')) or 0)/100)
            position=1. if proof.get('bbox') and proof.get('column_index') is not None else .4
            components={'ocr':ocr,'mapping':mapping,'position':position,'parser_agreement':1. if parsers>1 else 0.,
                        'independent_tables':independent,'accounting_passes':passed,'accounting_failures':failures}
            confidence=min(1.,.55*ocr+.25*mapping+.1*position+.05*(parsers>1)+.05*(independent>1)+.05*bool(passed))
            issues=list(failures)
            rejected_conflicts=[]
            if conflicting:
                def contradicted_alt(item):
                    _,r,ev=item
                    if period=='current' and r.get('section')=='cpc':
                        try:
                            a=decimal_or_none(r.get('operations_current'));b=decimal_or_none(r.get('operations_prior_period'));c=decimal_or_none(r.get('current'))
                            if None not in (a,b,c) and abs(a+b-c)>Decimal('.02'):
                                return True
                        except Exception: pass
                    return (ev.get('confidence') or 0)<35
                rejected_conflicts=[x for x in conflicting if contradicted_alt(x)]
                if len(rejected_conflicts)!=len(conflicting):
                    issues.append('conflicting_source_occurrence')
            if proof.get('repairs'): issues.append('numeric_text_repair_requires_confirmation')
            selected_row_consistent=proof.get('row_internal_consistency')==1
            conflict_rejectable=bool(conflicting) and (primary_pass or selected_row_consistent) and all(
                ((r.get('section')=='cpc' and period=='current' and
                  None not in (decimal_or_none(r.get('operations_current')),decimal_or_none(r.get('operations_prior_period')),decimal_or_none(r.get('current'))) and
                  abs(decimal_or_none(r.get('operations_current'))+decimal_or_none(r.get('operations_prior_period'))-decimal_or_none(r.get('current')))>Decimal('.02'))
                 or (ev.get('confidence') or 0)<35)
                for _,r,ev in conflicting)
            if entry.get('period_status',{}).get(period) in ('unparsed','conflict') and not conflict_rejectable and not reconstructed:
                issues.append('unresolved_source')
            accounting_support=[]
            for check in checks:
                if check['status']!='passed' or check.get('period')!=period or check.get('row_terms'):
                    continue
                terms=check.get('coefficients',{})
                if key not in terms or len(terms)<3:continue
                others=[k for k in terms if k!=key]
                def reliable_operand(k):
                    other=result['canonical'].get(k,{})
                    ev=other.get('evidence',{}).get(period,{})
                    contradicted=any(c['status']=='failed' and c.get('period')==period and k in c.get('involved_keys',[]) for c in checks)
                    return (other.get(period) is not None and other.get('period_status',{}).get(period)!='conflict'
                        and (ev.get('confidence') or 0)>=80 and not ev.get('repairs') and not contradicted)
                if all(reliable_operand(k) for k in others) and sum(Decimal(result['canonical'][k][period])!=0 for k in others)>=2:
                    accounting_support.append(check['check'])
            components['supported_accounting_checks']=accounting_support
            components['rejected_conflicting_occurrences']=len(rejected_conflicts)
            resolved_conflict=bool(conflicting) and (conflict_rejectable or (len(rejected_conflicts)==len(conflicting) and bool(accounting_support)))
            if issues and not reconstructed: status='suspect'
            elif reconstructed: status='cross_checked'
            elif value is None: status='extracted_unverified'
            elif resolved_conflict: status='cross_checked'
            elif independent>1 and mapping>=.9 and any((ev.get('confidence') or 0)>=60 for _,_,ev in same): status='cross_checked'
            elif accounting_support and mapping>=.9 and (ocr>=.6 or proof.get('structural_repair')=='split_merged_current_previous'): status='cross_checked'
            elif confidence>=.85 and ocr>=.85 and mapping>=.9: status='high_confidence'
            else: status='extracted_unverified'
            native_read=proof.get('parser')=='pymupdf'
            category=('missing' if value is None else
                      'source_inconsistent' if issues and native_read else
                      'extraction_suspect' if issues else
                      'coherent_verified' if status in ('high_confidence','cross_checked') else 'extracted_unverified')
            entry['value_diagnostics'][period]={'category':category,
                'transcription_status':'native_observed' if native_read else 'ocr_observed',
                'accounting_status':'failed' if failures else 'passed' if passed else 'not_evaluable',
                'conflicting_occurrences':len(conflicting), 'requires_review':status=='suspect'}
            entry['value_status'][period]=status
            entry['confidence_components'][period]=dict(components,fused_score=round(confidence,4))
            entry['quality_flags'].extend(period+':'+x for x in issues)
            if resolved_conflict:
                entry['quality_flags'].append(period+':conflicting_occurrences_rejected_by_row_and_accounting_consistency')
            if proof:
                proof['extraction_status']=proof.get('extraction_status',proof.get('status'))
                proof['quality_status']=status;proof['fused_confidence']=round(confidence,4)
            if period in ('current','previous'):
                entry['usable_'+period]=value if status in ('high_confidence','cross_checked') else None
        statuses=[entry['value_status'][p] for p in ('current','previous') if entry.get(p) is not None]
        entry['status']=next((s for s in ('suspect','extracted_unverified','high_confidence','cross_checked') if s in statuses),'extracted_unverified')
        # Row status summarizes issues; eligibility remains strictly per cell.
        entry['confidence_fusion_version']=2


class TargetedOllama:
    """Shared hard call budget. No contact unless an endpoint is configured."""
    def __init__(self, base_url, max_calls=4, timeout=30):
        self.base_url=base_url.rstrip('/') if base_url else None
        self.max_calls=max(0,max_calls);self.calls=0;self.timeout=timeout

    def request(self, model, prompt, images=None):
        if not self.base_url or self.calls>=self.max_calls: return None
        import urllib.request
        self.calls+=1
        body={'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0,'num_predict':128}}
        if images: body['images']=images
        req=urllib.request.Request(self.base_url+'/api/generate',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=self.timeout) as response:
            payload=json.loads(response.read(1_000_000))
        return json.loads(payload['response'])


def semantic_fallback(row, allowed_labels, client):
    """Suggestions only. Allowed labels must come from this section's aliases.
    Qwen never receives amounts and cannot modify a FinancialRow.
    """
    if row['section'] not in FINANCIAL_SECTIONS or row.get('canonical_key'): return None
    allowed={k:v for k,v in LABEL_ALIASES.get(row['section'],{}).items() if k in allowed_labels}
    if not allowed: return None
    answer=client.request('qwen3.5:9b',json.dumps({'task':'Choose the matching label or null; return only {"label":...}.',
        'section':row['section'],'source_label':row['label'],'allowed_labels':list(allowed)},ensure_ascii=False))
    if not isinstance(answer,dict) or set(answer)!={'label'} or answer['label'] not in allowed: return None
    return {'suggested_key':allowed[answer['label']],'label':answer['label'],'status':'semantic_suggestion_requires_review',
            'page':row['page'],'table_id':row['table_id'],'row_index':row['row_index'],'source_label':row['label']}


def render_suspect_cell(pdf_path, proof, page_record):
    """Recreate the extraction coordinate frame before cropping. Never guess."""
    import base64
    bbox=proof.get('bbox')
    if not bbox: raise ValueError('missing_cell_bbox')
    with fitz.open(pdf_path) as doc:
        page=doc[proof['page']-1]
        if proof.get('coordinate_space')=='pdf_points_unrotated':
            page.set_rotation(0)
            rect=fitz.Rect(bbox)&page.rect
            if rect.is_empty or rect.get_area()>page.rect.get_area()*.15: raise ValueError('not_a_targeted_cell')
            pix=page.get_pixmap(clip=rect,dpi=400,alpha=False)
            return base64.b64encode(pix.tobytes('png')).decode()
        if proof.get('coordinate_space')!='ocr_pixels_after_rotation_and_deskew': raise ValueError('unsupported_coordinate_space')
        import cv2
        import numpy as np
        dpi=page_record.get('dpi')
        if not dpi: raise ValueError('missing_original_dpi')
        pix=page.get_pixmap(dpi=dpi,colorspace=fitz.csGRAY,alpha=False)
        image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width).copy()
        image=rotate_image(image,page_record.get('rotation_clockwise',0))
        h,w=image.shape
        angle=page_record.get('deskew_counterclockwise',0)
        if angle:
            transform=cv2.getRotationMatrix2D((w/2,h/2),angle,1.)
            image=cv2.warpAffine(image,transform,(w,h),flags=cv2.INTER_CUBIC,borderValue=255)
        if page_record.get('ocr_image_size')!=[w,h]: raise ValueError('coordinate_frame_size_mismatch')
        x0,y0,x1,y1=map(int,bbox)
        if not (0<=x0<x1<=w and 0<=y0<y1<=h) or (x1-x0)*(y1-y0)>w*h*.15: raise ValueError('invalid_cell_bbox')
        roi=image[max(0,y0-3):min(h,y1+3),max(0,x0-3):min(w,x1+3)]
        roi=cv2.resize(roi,None,fx=max(1.,400/dpi),fy=max(1.,400/dpi),interpolation=cv2.INTER_CUBIC)
        ok,png=cv2.imencode('.png',roi)
        if not ok: raise ValueError('png_encode_failed')
        return base64.b64encode(png.tobytes()).decode()


def targeted_ocr_repair(result,pages,pdf_path,config):
    client=TargetedOllama(config.ollama_url,config.max_llm_calls,config.llm_timeout)
    records={p['page']:p for p in pages};audit=[];seen={}
    for key,entry in list(result['canonical'].items())+result.get('additional_suspect_values',[]):
        for period,status in entry['value_status'].items():
            if status!='suspect': continue
            if entry.get('value_diagnostics',{}).get(period,{}).get('category')=='source_inconsistent': continue
            ev=entry.get('evidence',{}).get(period,{})
            locator=tuple(ev.get(k) for k in ('page','table_id','row_index','column_index'))
            task={'key':key,'period':period,'original_value':entry.get(period),'evidence':ev,
                  'computed_candidates':entry['computed_candidates'].get(period,[]),'status':'queued', 'replacement_applied':False}
            audit.append(task)
            if locator in seen:
                task.update(status='duplicate_cell',linked_task=seen[locator]);continue
            seen[locator]=len(audit)-1
            if not client.base_url: task['status']='awaiting_ollama_endpoint';continue
            if client.calls>=client.max_calls: task['status']='budget_exhausted';continue
            try:
                crop=render_suspect_cell(pdf_path,ev,records[ev['page']])
                answer=client.request('glm-ocr:q8_0','Read only the printed amount in this cell. Return exactly {"raw":"printed text"}, or {"raw":null} if unreadable. No calculation, no inference.',[crop])
                if not isinstance(answer,dict) or set(answer)!={'raw'} or (answer['raw'] is not None and not isinstance(answer['raw'],str)):
                    raise ValueError('invalid_model_response')
                parsed=parse_amount(answer['raw'] or '',ocr=False)
                task.update(model='glm-ocr:q8_0',model_raw=answer['raw'],reread_value=parsed['value'],status='unconfirmed_reread')
                # Independent existing parser reading of the same cell is required.
                confirmations=[a for a in ev.get('ocr_attempts',[]) if a.get('value')==parsed['value'] and a.get('parser') not in (None,'glm-ocr:q8_0')]
                if parsed['value'] is not None and parsed['value']==entry.get(period):
                    task['status']='reread_agrees_original_equation_still_requires_review'
                elif parsed['value'] is not None and confirmations:
                    task.update(status='independently_confirmed_candidate',confirmed_candidate=parsed['value'])
                # Even confirmed candidates remain explicit; no mutation of printed observations.
            except Exception as exc:
                task.update(status='verification_error',error=type(exc).__name__+': '+str(exc)[:250])
    result['targeted_repairs']=audit
    result['llm_audit']={'calls':client.calls,'max_calls':client.max_calls,'endpoint_configured':bool(client.base_url),
                         'semantic_suggestions':[],'amount_replacements':0}
    if config.semantic_fallback:
        for row in result['all_rows']:
            if client.calls>=client.max_calls: break
            if row.get('row_kind')!='financial' or row.get('canonical_key') or row.get('source_parser')=='pymupdf': continue
            try:
                suggestion=semantic_fallback(row,LABEL_ALIASES.get(row['section'],{}),client)
                if suggestion: result['llm_audit']['semantic_suggestions'].append(suggestion)
            except Exception as exc:
                result['llm_audit'].setdefault('errors',[]).append(type(exc).__name__)
    result['llm_audit']['calls']=client.calls




def repair_short_section_labels(rows):
    """Four-letter OCR alias only inside the known personnel/tax/associate block."""
    grouped=defaultdict(list)
    for row in rows: grouped[(row.page,row.table_id,row.section)].append(row)
    for (_,_,section),items in grouped.items():
        if section not in ('bilan_actif','bilan_passif'): continue
        items.sort(key=lambda r:r.row_index)
        for i,row in enumerate(items):
            n=semantic_label(row.label)
            if row.canonical_key or row.source_parser=='pymupdf' or n not in ('ftat','feat','frat','fat'): continue
            if i==0 or i+1>=len(items):continue
            before,after=items[i-1],items[i+1]
            expected='personnel_debiteur' if section=='bilan_actif' else 'organismes_sociaux'
            next_key='comptes_associes_actif' if section=='bilan_actif' else 'comptes_associes_passif'
            if before.canonical_key==expected and after.canonical_key==next_key and after.row_index-before.row_index==2:
                row.canonical_key='etat_debiteur' if section=='bilan_actif' else 'etat_crediteur'
                row.mapping_method='section_and_adjacent_rows';row.match_score=94.
                row.warnings.append('short_ocr_label_confirmed_by_section_and_two_neighbors')
    return rows


def subtotal_lower_bounds(rows):
    """Debt subitems are nonnegative under this explicit presentation rule.
    Missing cells give a lower bound, never a zero-valued observation or equality.
    A compatible partial bound is NOT a passed complete accounting equation.
    """
    checks=[]
    for parent in rows:
        if parent.get('canonical_key')!='dettes_passif_circulant':continue
        children=sorted([r for r in rows if r['page']==parent['page'] and r['table_id']==parent['table_id']
            and parent['row_index']<r['row_index']<=parent['row_index']+8],key=lambda r:r['row_index'])
        if len(children)!=8 or not any(r.get('canonical_key')=='organismes_sociaux' for r in children):continue
        for period in ('current','previous'):
            values=[Decimal(r[period]) for r in children if r.get(period) is not None]
            total=decimal_or_none(parent.get(period));missing=[r['label'] for r in children if r.get(period) is None]
            bound=sum(values,Decimal(0)) if values else None
            difference=bound-total if total is not None and bound is not None else None
            status='not_evaluable'
            if difference is not None and all(v>=0 for v in values):
                if difference>Decimal('.02'):status='failed'
                elif not missing:status='passed' if abs(difference)<=Decimal('.02') else 'failed'
            checks.append({'check':'dettes_circulantes_subitems_'+period,'status':status,
                'ok':None if status=='not_evaluable' else status=='passed','difference':dec_str(difference),
                'known_subtotal':dec_str(bound),'printed_total':dec_str(total),'missing_inputs':missing,
                'period':period,'involved_keys':[r['canonical_key'] for r in [parent]+children if r.get('canonical_key')],
                'coefficients':{},'tolerance':'0.02','rule':'nonnegative_debt_subitems_lower_bound',
                'assumption':'unprinted debt subitems are nonnegative, not necessarily zero',
                'cell_locators':[{k:r[k] for k in ('page','table_id','row_index')} for r in [parent]+children]})
    return checks


def add_business_cross_checks(result):
    # Only semantically identical observations, never arbitrary repeated numbers.
    for key,block,field in [('resultat_net','resultat_fiscal','resultat_net_comptable'),('capital','capital_repartition','capital_social')]:
        proofs=result[block].get('evidence',{}).get(field,[])
        for ev in proofs:
            if ev.get('source_view')=='text_line' and any(p.get('table_id') is not None and p.get('page')==ev['page'] for p in proofs): continue
            value=ev.get('value')
            if value is None: continue
            row={'page':ev['page'],'table_id':ev['table_id'],'row_index':ev['row_index'],
                 'section':block,'label':field,'source_parser':ev['parser'],'current':value,
                 'evidence':{'current':ev},'mapping_method':'explicit_business_schema','match_score':100.}
            result['canonical_candidates'].setdefault(key,[]).append(row)


def annotate_business_and_unmapped(result, rows):
    additional=[]
    def suspect(path,proof,value,candidates=None):
        proof['quality_status']='suspect'
        additional.append((path,{'current':value,'value_status':{'current':'suspect'},
            'evidence':{'current':proof},'computed_candidates':{'current':candidates or []}}))
    for row in rows:
        for period,proof in row.get('evidence',{}).items():
            if not isinstance(proof,dict): continue
            proof.update(page=row['page'],table_id=row['table_id'],row_index=row['row_index'],parser=row['source_parser'])
        for check in result['validations']:
            if check.get('row_terms') and check['status']=='failed' and all(row[k]==check[k] for k in ('page','table_id','row_index')):
                for period,coefficient in check['coefficients'].items():
                    proof=row['evidence'].get(period,{})
                    val=row.get(period)
                    candidate=dec_str(Decimal(val)-Decimal(check['difference'])/Decimal(coefficient)) if val is not None else None
                    suspect(f'all_rows/{row["page"]}/{row["table_id"]}/{row["row_index"]}/{period}',proof,val,
                        [{'value':candidate,'check':check['check'],'status':'hypothesis_requires_targeted_verification'}])
    def annotate(node,path):
        if isinstance(node,list):
            for i,v in enumerate(node): annotate(v,path+'/'+str(i))
        elif isinstance(node,dict):
            if 'raw' in node and 'value' in node and 'parser' in node:
                confidence=node.get('confidence')
                if node.get('repairs') or node.get('status') in ('unparsed','invalid_identifier'):
                    status='suspect'
                elif node['value'] is not None and confidence is not None and confidence>=90 and not node.get('schema_method'): status='high_confidence'
                else: status='extracted_unverified'
                node['quality_status']=status
                if status=='suspect' and node.get('value_kind')=='amount': suspect(path,node,node['value'])
            else:
                for k,v in node.items(): annotate(v,path+'/'+k)
    annotate(result['resultat_fiscal'],'resultat_fiscal')
    annotate(result['capital_repartition'],'capital_repartition')
    for check in result['validations']:
        if check['status']!='failed' or check.get('business_section')!='resultat_fiscal': continue
        fiscal=result['resultat_fiscal']
        fiscal['quality_flags'].append(check['check'])
        blocks=[k for k in ('reintegrations_fiscales','deductions_fiscales') if k in check['check']]
        for key in blocks:
            data=fiscal[key]
            for ev in data.get('evidence',{}).get('total',[]): suspect('resultat_fiscal/'+key+'/total',ev,data['total'])
            for i,detail in enumerate(data['details']): suspect(f'resultat_fiscal/{key}/details/{i}',detail['evidence'],detail['amount'])
        if check['check']=='fiscal_resultat_brut':
            for key in ('resultat_net_comptable','resultat_brut_fiscal'):
                for ev in fiscal['evidence'].get(key,[]): suspect('resultat_fiscal/'+key,ev,fiscal[key])
    result['additional_suspect_values']=additional



def reconcile_business_outputs(result):
    """Cross-link business views with canonical fields without hiding source evidence."""
    fiscal=result.get('resultat_fiscal',{})
    canonical=result.get('canonical',{})
    # Same semantic concept: net accounting result in fiscal bridge equals current result net.
    cnet=canonical.get('resultat_net',{}).get('current')
    if cnet is not None:
        fnet=fiscal.get('resultat_net_comptable')
        if fnet is None:
            fiscal['resultat_net_comptable']=cnet
            src=canonical.get('resultat_net',{}).get('evidence',{}).get('current',{})
            fiscal.setdefault('evidence',{}).setdefault('resultat_net_comptable',[]).append({
                'value':cnet,'raw':src.get('raw',cnet),'status':'cross_section_reference','parser':'canonical_reconciliation',
                'source_key':'resultat_net','value_kind':'amount','page':src.get('page'),
                'table_id':src.get('table_id'),'row_index':src.get('row_index'),'column_index':src.get('column_index'),
                'bbox':src.get('bbox'),'coordinate_space':src.get('coordinate_space'),'confidence':src.get('confidence')})
            fiscal.setdefault('quality_flags',[]).append('resultat_net_comptable_recovered_from_same_semantic_canonical_field')
        elif Decimal(fnet)!=Decimal(cnet):
            supports={r.get('section') for r in result.get('canonical_candidates',{}).get('resultat_net',[]) if r.get('current')==cnet}
            if len(supports)>=2:
                fiscal['resultat_net_comptable_original_observation']=fnet
                fiscal['resultat_net_comptable']=cnet
                src=canonical.get('resultat_net',{}).get('evidence',{}).get('current',{})
                fiscal.setdefault('evidence',{}).setdefault('resultat_net_comptable',[]).append({
                    'value':cnet,'raw':src.get('raw',cnet),'status':'cross_section_consensus_resolution','parser':'canonical_reconciliation',
                    'source_key':'resultat_net','value_kind':'amount','page':src.get('page'),'table_id':src.get('table_id'),
                    'row_index':src.get('row_index'),'column_index':src.get('column_index'),'bbox':src.get('bbox'),
                    'coordinate_space':src.get('coordinate_space'),'confidence':src.get('confidence')})
                fiscal.setdefault('quality_flags',[]).append('resultat_net_comptable_resolved_by_cross_section_consensus')
            else:
                fiscal.setdefault('quality_flags',[]).append('resultat_net_comptable_conflicts_with_canonical_resultat_net')
    capital=result.get('capital_repartition',{})
    ccapital=canonical.get('capital',{}).get('current')
    if capital.get('capital_social') is None and ccapital is not None:
        capital['capital_social']=ccapital
        src=canonical.get('capital',{}).get('evidence',{}).get('current',{})
        capital.setdefault('evidence',{}).setdefault('capital_social',[]).append({
            'value':ccapital,'raw':src.get('raw',ccapital),'status':'cross_section_reference','parser':'canonical_reconciliation',
            'source_key':'capital','value_kind':'amount','page':src.get('page'),
            'table_id':src.get('table_id'),'row_index':src.get('row_index'),'column_index':src.get('column_index'),
            'bbox':src.get('bbox'),'coordinate_space':src.get('coordinate_space'),'confidence':src.get('confidence')})
        capital.setdefault('quality_flags',[]).append('capital_social_recovered_from_balance_sheet_same_semantic_field')

def enrich_dossier(result,pages,pdf_path,config):
    original_rows=result['all_rows']
    result['resultat_fiscal']=parse_resultat_fiscal(pages)
    result['capital_repartition']=parse_capital_repartition(pages)
    reconcile_business_outputs(result)
    result['source_precision_diagnostics']=source_precision_diagnostics(result['canonical_candidates'])
    result['legacy_validations']=result['validations']
    result['validations']=accounting_validation(result['canonical'],original_rows,result['resultat_fiscal'])
    result['validations'].extend(subtotal_lower_bounds(original_rows))
    add_business_cross_checks(result)
    result['validations'].extend(inter_section_checks(result['canonical_candidates']))
    result['validations'].extend(equity_component_checks(original_rows))
    if apply_two_constraint_reconstructions(result):
        # Re-evaluate equations against the explicitly resolved canonical view.
        result['validations']=accounting_validation(result['canonical'],original_rows,result['resultat_fiscal'])
        result['validations'].extend(subtotal_lower_bounds(original_rows))
        result['validations'].extend(inter_section_checks(result['canonical_candidates']))
        result['validations'].extend(equity_component_checks(original_rows))
    confidence_fusion(result)
    annotate_business_and_unmapped(result,original_rows)
    result['all_rows']=document_rows(pages,original_rows)
    targeted_ocr_repair(result,pages,pdf_path,config)
    result['derived']=compute_derived(result['canonical'])
    result['schema_version']=VERSION
    quality=result['quality']
    for status in ('passed','failed','not_evaluable'):
        quality[status+'_check_count']=sum(c['status']==status for c in result['validations'])
    quality['usable_current_count']=sum(v['usable_current'] is not None for v in result['canonical'].values())
    quality['suspect_field_count']=sum(v['status']=='suspect' for v in result['canonical'].values())
    quality['cross_checked_current_count']=sum(v['value_status']['current']=='cross_checked' for v in result['canonical'].values())
    quality['all_rows_count']=len(result['all_rows'])
    quality['unverified_current_count']=sum(v.get('current') is not None and v['value_status'].get('current')=='extracted_unverified' for v in result['canonical'].values())
    if quality['status']!='incomplete' and (quality['failed_check_count'] or quality['suspect_field_count'] or quality['unverified_current_count']): quality['status']='issues_detected'
    result['audit_policy']={'no_silent_numeric_replacement':True,'blank_is_not_zero':True,
        'computed_candidates_are_observations':False,'ratios_use_usable_values_only':True,
        'observed_values_preserved_when_reconstructed':True,'reconstruction_requires_two_independent_constraints':True,
        'cross_check_independence':'same canonical meaning and period, distinct page/table',
        'all_rows_views':['financial','physical_table','text_line']}



def classify_page_structure(text, initial=None):
    """Independent form cues, without using amounts or a global fuzzy match."""
    section=initial or detect_section(text)
    n=normalize_label(text)
    codes=set(re.findall(r'\b(611|612|613|614|616|617|618|619|711|712|713|718|719)\s*[-—–]',text))
    detail_cues=sum(cue in n for cue in ('achats de marchandises','variation des stocks de marchandises','reste du poste','detail du poste'))
    if (len(codes)>=3 or detail_cues>=3) and not ('operations propres' in n or 'totaux de l exercice' in n):
        return 'detail_cpc'
    if 'repartition' in n and 'capital social' in n and ('associes' in n or 'titres' in n):
        return 'capital_repartition'
    return section



DGI_REFERENCE_LABELS = {'bilan_actif': {'immobilisations en non valeurs a': 'immobilisations_non_valeurs', 'immobilisations incorporelles b': 'immobilisations_incorporelles', 'immobilisations corporelles c': 'immobilisations_corporelles', 'mobilier materiel de bureau et amenagement divers': 'mobilier_materiel_bureau', 'immobilisations corporelles en cours': 'immobilisations_corporelles_en_cours', 'immobilisations financieres d': 'immobilisations_financieres', 'autres creances financieres': 'autres_creances_financieres', 'titres de participation': 'titres_participation', 'matieres et fournitures consommables': 'matieres_fournitures_consommables', 'creances de l actif circulant g': 'creances_actif_circulant', 'fournis debiteurs avances et acomptes': 'fournisseurs_debiteurs', 'clients et comptes rattaches': 'clients', 'comptes d associes': 'comptes_associes_actif', 'autres debiteurs': 'autres_debiteurs', 'comptes de regularisation actif': 'cca_actif', 'titres valeurs de placement h': 'titres_valeurs_placement', 'tresorerie actif': 'tresorerie_actif', 'banques t g et c c p': 'banques_actif', 'caisse regie d avances et accreditifs': 'caisse'}, 'bilan_passif': {'capital social ou personnel 1': 'capital', 'reserve legale': 'reserve_legale', 'autres reserves': 'autres_reserves', 'report a nouveau 2': 'report_a_nouveau', 'resultat net de l exercice 2': 'resultat_net', 'capitaux propres assimiles b': 'capitaux_propres_assimiles', 'dettes de financement c': 'dettes_financement', 'emprunts obligataires': 'emprunts_obligataires', 'autres dettes de financement': 'autres_dettes_financement', 'dettes du passif circulant f': 'dettes_passif_circulant', 'fournisseurs et comptes rattaches': 'fournisseurs', 'clients crediteurs avances et acomptes': 'clients_crediteurs', 'organismes sociaux': 'organismes_sociaux', 'comptes d associes': 'comptes_associes_passif', 'autres creanciers': 'autres_crediteurs', 'comptes de regularisation passif': 'cca_passif', 'autres provisions pour risques et charges g': 'autres_provisions_risques_charges', 'credits d escompte': 'credits_escompte', 'credits de tresorerie': 'credits_tresorerie', 'banques soldes crediteurs': 'banques_passif'}, 'cpc': {'ventes de marchandises en l etat': 'ventes_marchandises', 'ventes de biens et services produits': 'ventes_biens_services', 'chiffres d affaires': 'chiffre_affaires', 'variation de stocks de produits 1': 'variation_stock_produits', 'achats revendus 2 de marchandises': 'achats_rev_marchandises', 'achats consommes 2 de matieres et fournitures': 'achats_consommes', 'autres charges externes': 'autres_charges_externes', 'impots et taxes': 'impots_taxes', 'charges de personnel': 'charges_personnel', 'dotations d exploitation': 'dotations_exploitation', 'iii resultat d exploitation i ii': 'resultat_exploitation', 'interets et autres produits financiers': 'interets_autres_produits_financiers', 'charges d interets': 'charges_interets', 'vi resultat financier iv v': 'resultat_financier', 'vii resultat courant iii vi': 'resultat_courant', 'viii produits non courants': 'produits_non_courants', 'autres produits non courants': 'autres_produits_non_courants', 'x resultat non courant viii ix': 'resultat_non_courant', 'xi resultat avant impots vii x': 'resultat_avant_impots', 'xii impots sur les resultats': 'impots_resultats', 'resultat net xi xii': 'resultat_net'}, 'esg': {'7 autres charges externes': 'autres_charges_externes', 'iv valeur ajoutee i ii iii': 'valeur_ajoutee', '9 impots et taxes': 'impots_taxes', '10 charges de personnel': 'charges_personnel', 'v excedent brut d exploitation ebe ou insuffisance brute d exploitation ibe': 'ebe', '14 dotations d exploitation': 'dotations_exploitation', 'vi resultat d exploitation ou': 'resultat_exploitation', 'vii resultat financier': 'resultat_financier', 'ix resultat non courant': 'resultat_non_courant', '15 impots sur les resultats': 'impots_resultats', 'x resultat net de l exercice': 'resultat_net', '1 resultat net de l exercice': 'resultat_net', 'i capacite d autofinancement c a f': 'caf', 'ii autofinancement': 'autofinancement'}, 'detail_cpc': {'locations et charges locatives': 'locations_charges_locatives', 'redevances de credit bail': 'redevances_credit_bail', '617 charges de personnel': 'charges_personnel', '738 interets et autres produits financiers': 'interets_autres_produits_financiers'}}

def map_scoped_noisy_labels(rows):
    for row in rows:
        if row.section=='detail_cpc' and row.source_parser!='pymupdf' and re.search(r'\b61[1278]\s*[-—–]',row.label):
            if row.canonical_key in {'achats_consommes','achats_rev_marchandises','charges_personnel','autres_charges_externes'}:
                row.warnings.append('detail_account_heading_not_cpc_total');row.canonical_key=None
            continue
        if row.canonical_key or row.source_parser=='pymupdf' or row.section not in FINANCIAL_SECTIONS:continue
        n=normalize_label(row.label)
        if len(n)<12 or 'dont' in n or 'reste du poste' in n:continue
        allowed={**DGI_REFERENCE_LABELS.get(row.section,{}),**LABEL_ALIASES.get(row.section,{})}
        scores=[]
        tokens=n.split()
        for alias,key in allowed.items():
            alias=normalize_label(alias)
            if len(alias)<14 or alias.startswith('total'):continue
            size=len(alias.split())
            windows=[' '.join(tokens[i:i+j]) for j in range(max(2,size-1),size+2) for i in range(max(1,len(tokens)-j+1))]
            score=max([SequenceMatcher(None,n,alias).ratio()]+[SequenceMatcher(None,w,alias).ratio() for w in windows])
            scores.append((score,key,alias))
        scores.sort(reverse=True)
        if not scores:continue
        best=scores[0];other=next((v[0] for v in scores if v[1]!=best[1]),0)
        if best[0]>=.9 and best[0]-other>=.06:
            row.canonical_key=best[1];row.mapping_method='section_scoped_dgi_label_window'
            row.match_score=round(best[0]*100,2);row.warnings.append('source_label_matched:'+best[2])
    return rows

def recover_passif_continuations(pages):
    """A two-period closing total on an immediately following passif page.
    No fuzzy global classification, no invented cell geometry/confidence.
    """
    ordered=sorted(pages,key=lambda p:p['page'])
    for prior,page in zip(ordered,ordered[1:]):
        if prior['section']!='bilan_passif' or page['page']!=prior['page']+1 or page['section']!='generic' or page.get('rows'):continue
        text=normalize_label(page.get('text',''))
        if 'exercice' not in text or 'precedent' not in text or 'capital personnel debiteur' not in text:continue
        for ri,line in enumerate(page.get('text','').splitlines()):
            if not re.search(r'total\s*general',normalize_label(line)):continue
            matches=list(re.finditer(r'(?<!\d)(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)[,.]\d{2}(?!\d)',line))
            if len(matches)!=2:continue
            evidence={}
            for period,match in zip(('current','previous'),matches):
                proof=parse_amount(match.group(),ocr=page['parser']!='pymupdf')
                proof.update(page=page['page'],table_id=-1,row_index=ri,column_index=None,bbox=None,
                    parser=page['parser'],confidence=100 if page['parser']=='pymupdf' else None,
                    source_view='text_line',raw_line=line,text_span=list(match.span()))
                evidence[period]=proof
            row=FinancialRow(page=page['page'],section='bilan_passif',label='TOTAL GENERAL',group_label='',
                table_id=-1,row_index=ri,canonical_key='total_passif',source_parser=page['parser'],
                current=evidence['current']['value'],previous=evidence['previous']['value'],evidence=evidence,
                mapping_method='passif_continuation_two_period_total',match_score=96.,confidence=.5)
            page['rows']=[dataclasses.asdict(row)];page['section']='bilan_passif'
            page.setdefault('warnings',[]).append('total_recovered_from_text_line_without_cell_bbox')
            break


def contextual_total_mapping(rows):
    groups=defaultdict(list)
    for row in rows:groups[(row.page,row.table_id,row.section)].append(row)
    for (_,_,section),items in groups.items():
        if section not in ('bilan_actif','bilan_passif'):continue
        items.sort(key=lambda r:r.row_index)
        for i,row in enumerate(items):
            if row.source_parser=='pymupdf':continue
            n=normalize_label(row.label)
            old=row.canonical_key; key=None
            if 'total des capitaux propres' in n and section=='bilan_passif':key='fonds_propres'
            if re.search(r'[ft]otal\s*general',n):key='total_actif' if section=='bilan_actif' else 'total_passif'
            if section=='bilan_actif' and n.startswith('total') and 'general' not in n:
                recent=items[max(0,i-4):i]
                if any(r.canonical_key=='banques_actif' or 'banques' in normalize_label(r.label) for r in recent) and any('caisse' in normalize_label(r.label) for r in recent):
                    key='tresorerie_actif'
            if section=='bilan_passif' and 'total' in n and 'general' not in n:
                recent=items[max(0,i-3):i]
                # Printed cash/bank labels establish the block, despite II/III OCR.
                if any(r.canonical_key=='banques_passif' for r in recent) and not re.search(r'f\s*\+\s*g',n):
                    key='tresorerie_passif'
                elif re.search(r'f\s*\+\s*g\s*\+\s*h',n):key='total_passif_circulant'
            if key and key!=old:
                row.canonical_key=key;row.mapping_method='printed_label_and_block_context';row.match_score=96.
                row.warnings.append('mapping_revision:'+str(old)+'->'+key)
    return rows


def enrich_identity_identifiers(person):
    """Spaces in a printed IF are typography, not a guessed identifier."""
    for proof in person.get('evidence',{}).get('if',[]):
        raw=proof.get('raw','').strip()
        if raw and re.fullmatch(r'\d[\d\s]*',raw):
            value=re.sub(r'\s','',raw)
            if len(value)<=15:
                proof.update(value=value,status='observed',normalization='printed_identifier_whitespace')
    values={p['value'] for p in person.get('evidence',{}).get('if',[]) if p.get('value') is not None}
    if len(values)==1:
        person['if']=next(iter(values))
        person['quality_flags']=[f for f in person['quality_flags'] if f!='invalid_if_text']
    return person


def source_precision_diagnostics(candidates):
    """Describe rounding-compatible source disagreements; do not resolve them."""
    out=[]
    for key,rows in candidates.items():
        for period in ('current','previous'):
            observed=[(Decimal(r[period]),r) for r in rows if r.get(period) is not None]
            values={v for v,_ in observed}
            if len(values)<2:continue
            integers={v for v in values if v==v.to_integral_value()}
            if integers and max(values)-min(values)<=Decimal('.5') and len({v.quantize(Decimal('1')) for v in values})==1:
                out.append({'key':key,'period':period,'status':'rounding_compatible_not_resolved',
                    'values':sorted(str(v) for v in values),'note':'Printed values differ; rounding is plausible but not proven.'})
    return out


class FinancialPDFExtractor:
    def __init__(self,output_root: Path,config: Config | None = None,jobs: int = 2):
        self.output_root = Path(output_root)
        self.config = config or Config()
        self.jobs = max(1,jobs)

    def extract(self,pdf_path: Path,pages: list[int] | None = None) -> dict:
        path = Path(pdf_path).resolve(strict=True)
        digest = sha256_file(path)
        started = time.monotonic()
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise ValueError('PDF protégé par mot de passe : fournissez une copie accessible.')
            page_count = len(doc)
            selected = list(range(page_count)) if pages is None else sorted({p-1 for p in pages})
            if not selected or min(selected)<0 or max(selected)>=page_count:
                raise ValueError(f'Sélection de pages invalide ; le document contient {page_count} pages.')
            needs_ocr = self.config.ocr == 'always' or (self.config.ocr != 'never' and any(len(doc[p].get_text('words')) < 60 for p in selected))
        engine = tesseract_info(self.config) if needs_ocr else {'version':'not_used'}
        fingerprint = hashlib.sha256(json.dumps({'version':CACHE_VERSION,'source':digest,'config':dataclasses.asdict(self.config),
                         'pymupdf':fitz.__version__,'ocr':engine},sort_keys=True).encode()).hexdigest()
        out_dir = self.output_root/safe_stem(path,digest)
        cache_dir = out_dir/'.cache'/fingerprint[:16]
        tasks = [(str(path),i,dataclasses.asdict(self.config),str(cache_dir/f'page_{i+1:03d}.json'),fingerprint) for i in selected]
        page_records = []
        if self.jobs == 1:
            for task in tasks:
                record = page_worker(*task)
                page_records.append(record)
                LOG.info('%s : page %s/%s (%s, %s lignes)',path.name,record['page'],page_count,record['section'],len(record['rows']))
        else:
            # PyMuPDF is not shared across threads: each process opens its PDF.
            with ProcessPoolExecutor(max_workers=self.jobs) as pool:
                futures = [pool.submit(page_worker,*task) for task in tasks]
                for future in as_completed(futures):
                    record = future.result()
                    page_records.append(record)
                    LOG.info('%s : page %s/%s (%s, %s lignes)',path.name,record['page'],page_count,record['section'],len(record['rows']))
        page_records.sort(key=lambda p:p['page'])
        recover_passif_continuations(page_records)
        rows = [FinancialRow(**row) for page in page_records for row in page['rows']]
        map_scoped_noisy_labels(rows)
        contextual_total_mapping(rows)
        repair_short_section_labels(rows)
        canonical,candidates,conflicts = resolve_canonical(rows)
        identity = dataclasses.asdict(Identity())
        identity_conflicts = []
        for page in page_records:
            # Repeated headers corroborate identity; conflicting IDs are kept
            # separately rather than replacing the first identity silently.
            secondary = clean_identity(page['text'])
            for key,value in secondary.items():
                if key == 'evidence' or value is None:
                    continue
                if identity.get(key) is None:
                    identity[key] = value
                    identity['evidence'][key] = {'page':page['page'],'raw':value}
                elif identity[key] != value and key in {'identifiant_fiscal','ice','period_start','period_end'}:
                    identity_conflicts.append({'field':key,'page':page['page'],'value':value,'selected':identity[key]})
        validations = validate(canonical,rows)
        apply_validation_flags(canonical,validations)
        derived = compute_derived(canonical)
        missing = [k for k in REQUIRED_FIELDS if k not in canonical]
        blank = [k for k in REQUIRED_FIELDS if k in canonical and all(canonical[k]['period_status'].get(p) in {'blank','dash','missing_cell'} for p in ('current','previous'))]
        page_errors = sum(bool(p['errors']) for p in page_records)
        failed_checks = sum(v['status']=='failed' for v in validations)
        low_conf = sum(c['period_status'].get('current') in {'low_confidence','unparsed'} for c in canonical.values())
        financial_pages = [p for p in page_records if p['section'] in FINANCIAL_SECTIONS]
        complete_scope = len(selected) == page_count
        context_warnings = []
        if any('previsionnel' in normalize_label(p.get('text','')) for p in page_records):
            context_warnings.append('forecast_statements_present_use_page_selection_to_isolate_each_statement_set')
        quality_status = 'incomplete' if page_errors or not financial_pages or not complete_scope else 'issues_detected' if conflicts or failed_checks or missing or low_conf or identity_conflicts or context_warnings else 'checks_passed'
        quality = {'status':quality_status,'scope':'full_document' if complete_scope else 'selected_pages',
                   'canonical_field_count':len(canonical),'observed_current_count':sum(v['current'] is not None for v in canonical.values()),
                   'usable_current_count':sum(v['usable_current'] for v in canonical.values()),
                   'financial_page_count':len(financial_pages),'error_page_count':page_errors,
                   'conflict_count':len(conflicts),'failed_check_count':failed_checks,
                   'passed_check_count':sum(v['status']=='passed' for v in validations),
                   'not_evaluable_check_count':sum(v['status']=='not_evaluable' for v in validations),
                   'low_confidence_or_unparsed_current_count':low_conf,
                   'context_warnings':context_warnings,
                   'note':'Heuristic diagnostics; checks_passed is not a guarantee of transcription accuracy.'}
        result = {'schema_version':VERSION,'source':{'file':str(path),'sha256':digest,'pages':page_count,
                  'processed_pages':[p['page'] for p in page_records],'amount_unit':source_units(page_records)},
                  'runtime':{'pymupdf':fitz.__version__,'ocr':engine,'config':dataclasses.asdict(self.config),
                             'elapsed_seconds':round(time.monotonic()-started,3)},
                  'identity':identity,'identity_conflicts':identity_conflicts,
                  'canonical':canonical,'canonical_candidates':candidates,'derived':derived,
                  'quality':quality,'validations':validations,'conflicts':conflicts,
                  'missing_required_fields':missing,'present_but_blank_fields':blank,
                  'all_rows':[dataclasses.asdict(r) for r in rows],
                  'pages':[{k:v for k,v in p.items() if k not in {'text','rows','tables'}} for p in page_records],
                  'output_directory':str(out_dir.resolve())}
        enrich_dossier(result,page_records,path,self.config)
        result["runtime"]["elapsed_seconds"] = round(time.monotonic()-started,3)
        write_outputs(out_dir,result,page_records)
        return result


def parse_pages(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    pages = set()
    for token in spec.split(','):
        if re.fullmatch(r'\d+',token):
            pages.add(int(token))
        elif re.fullmatch(r'\d+-\d+',token):
            left,right = map(int,token.split('-'))
            if right<left or right-left>10000:
                raise ValueError('Intervalle de pages invalide')
            pages.update(range(left,right+1))
        else:
            raise ValueError('Utilisez --pages 1-5,8,10')
    if not pages or min(pages)<1:
        raise ValueError('La première page porte le numéro 1')
    return sorted(pages)



def pages_from_extraction(snapshot, min_confidence=60):
    """Rebuild the physical cell view, never the lossy canonical CSV."""
    import copy
    pages={p['page']:copy.deepcopy(p) for p in snapshot['pages']}
    tables={};texts=defaultdict(list)
    for p in pages.values():p.update(tables=[],rows=[],text='')
    for row in snapshot.get('all_rows',[]):
        page=row['page']
        if row.get('row_kind')=='text_line':texts[page].append((row['row_index'],row['raw']))
        if row.get('row_kind')!='physical_table':continue
        tid=row['table_id'];table=tables.setdefault((page,tid),{'table_id':tid,'cells':[], 'bbox':None,
            'coordinate_space':None,'section':row.get('section',pages[page]['section'])})
        ri=row['row_index']
        while len(table['cells'])<=ri:table['cells'].append([])
        cells=[]
        for proof in row.get('cells',[]):
            cell={'text':proof.get('raw',''),'bbox':proof.get('bbox'),'confidence':proof.get('confidence'),
                'missing_geometry':proof.get('status')=='missing_cell','ocr_attempts':copy.deepcopy(proof.get('ocr_attempts',[]))}
            table['coordinate_space']=proof.get('coordinate_space') or table['coordinate_space']
            # Restore an originally printed Unicode minus rejected by 3.1.
            attempts=cell['ocr_attempts']
            original=next((a for a in attempts if a.get('text','').lstrip().startswith('—') and (a.get('confidence') or 0)>=min_confidence),None)
            if original and parse_amount_ocr_relaxed(original['text'])['value'] is not None:
                old=cell['text'];cell['text']=original['text'];cell['confidence']=original['confidence']
                cell['unicode_sign_recovery']={'previous_selected_raw':old,'source_raw':original['text'],
                    'reason':'Unicode em dash normalized as printed minus; no arithmetic correction'}
            # V6 safety: if the selected retry has virtually no OCR confidence while
            # the original observation was high-confidence but ambiguous, restore the
            # original raw text instead of keeping an implausible numeric hallucination.
            selected_conf=cell.get('confidence') or 0
            best_original=max(attempts,key=lambda a:a.get('confidence') or 0,default=None)
            if selected_conf<20 and best_original and (best_original.get('confidence') or 0)>=min_confidence and best_original.get('text')!=cell.get('text'):
                old=cell['text'];cell['text']=best_original['text'];cell['confidence']=best_original['confidence']
                cell['reading_selection']={'original_raw':best_original['text'],'selected_raw':best_original['text'],
                    'method':best_original.get('method'),'reason':'restored_high_confidence_ambiguous_original_over_zero_confidence_numeric_retry',
                    'previous_selected_raw':old,'arithmetic_used':False}
            cells.append(cell)
        table['cells'][ri]=cells
    if not tables:raise ValueError('Reprocessing requires physical_table cells in all_rows; use the PDF for v3.0 exports.')
    for (page,tid),table in sorted(tables.items()):pages[page]['tables'].append(table)
    for number,p in pages.items():
        p['text']='\n'.join(t for _,t in sorted(texts[number]));p['section']=classify_page_structure(p['text'],p['section'])
        rows=[]
        for t in p['tables']:
            if p['section'] in ('detail_cpc','capital_repartition'):t['section']=p['section']
            repair_merged_two_period_rows(t,t['section'])
            rr,diag=rows_from_cells(t,t['section'],number,p['parser'],min_confidence)
            rows.extend(dataclasses.asdict(r) for r in rr)
        p['rows']=rows
        if rows:p['errors']=[e for e in p.get('errors',[]) if e!='financial_table_unresolved']
    recover_passif_continuations(list(pages.values()))
    return sorted(pages.values(),key=lambda p:p['page'])


def reprocess_extraction(snapshot_path,pdf_path,output_root,config,repair_missing_pages=False):
    import copy
    snapshot=json.loads(Path(snapshot_path).read_text(encoding='utf8'))
    if sha256_file(Path(pdf_path))!=snapshot['source']['sha256']:
        raise ValueError('PDF hash does not match the supplied extraction snapshot')
    pages=pages_from_extraction(snapshot,config.min_ocr_confidence)
    page_repairs=[]
    if repair_missing_pages:
        pending=[p for p in pages if p['section'] in FINANCIAL_SECTIONS and not p['rows'] and ('financial_table_unresolved' in p.get('errors',[]) or not p['tables'])]
        if pending:
            engine=tesseract_info(config)
            fingerprint=hashlib.sha256(json.dumps({'source':snapshot['source']['sha256'],'config':dataclasses.asdict(config),'version':CACHE_VERSION,'engine':engine},sort_keys=True).encode()).hexdigest()
            for original in pending[:2]:
                number=original['page']
                fresh=page_worker(str(Path(pdf_path).resolve()),number-1,dataclasses.asdict(config),
                    str(Path(output_root)/'.repair_cache'/fingerprint/f'page_{number}.json'),fingerprint)
                accepted=bool(fresh.get('rows')) and not fresh.get('errors')
                page_repairs.append({'page':number,'status':'recovered' if accepted else 'still_unresolved',
                    'engine':engine,'errors':fresh.get('errors',[]),'rows':len(fresh.get('rows',[]))})
                if accepted:pages[pages.index(original)]=fresh
    rows=[FinancialRow(**r) for p in pages for r in p['rows']]
    map_scoped_noisy_labels(rows);contextual_total_mapping(rows);repair_short_section_labels(rows)
    canonical,candidates,conflicts=resolve_canonical(rows)
    result=copy.deepcopy(snapshot)
    result.update(canonical=canonical,canonical_candidates=candidates,conflicts=conflicts,
        all_rows=[dataclasses.asdict(r) for r in rows],validations=validate(canonical,rows),
        missing_required_fields=[k for k in REQUIRED_FIELDS if k not in canonical],present_but_blank_fields=[])
    result['present_but_blank_fields']=[k for k in REQUIRED_FIELDS if k in canonical and all(canonical[k]['period_status'].get(p) in {'blank','dash','missing_cell'} for p in ('current','previous'))]
    result['quality'].update(low_confidence_or_unparsed_current_count=sum(v['period_status'].get('current') in {'low_confidence','unparsed'} for v in canonical.values()),canonical_field_count=len(canonical),observed_current_count=sum(v['current'] is not None for v in canonical.values()),
        conflict_count=len(conflicts),error_page_count=sum(bool(p.get('errors')) for p in pages),
        financial_page_count=sum(p['section'] in FINANCIAL_SECTIONS for p in pages))
    result['quality']['status']='incomplete' if result['quality']['error_page_count'] else 'issues_detected' if conflicts or result['missing_required_fields'] else 'checks_passed'
    enrich_dossier(result,pages,pdf_path,config)
    result['reprocessing_audit']={'input_sha256':sha256_file(Path(snapshot_path)),
        'mode':'physical_cells_reprocessed_without_page_OCR','prior_schema_version':snapshot['schema_version'],
        'prior_quality':snapshot['quality'],'page_repair_attempts':page_repairs,'canonical_value_revisions':[]}
    for key in sorted(set(snapshot['canonical'])|set(canonical)):
        for period in VALUE_NAMES:
            before=snapshot['canonical'].get(key,{}).get(period);after=canonical.get(key,{}).get(period)
            if before!=after:result['reprocessing_audit']['canonical_value_revisions'].append({'key':key,'column':period,'before':before,'after':after})
    out=Path(output_root)/safe_stem(Path(pdf_path),snapshot['source']['sha256'])
    result['output_directory']=str(out.resolve());result['pages']=[{k:v for k,v in p.items() if k not in ('text','tables','rows')} for p in pages]
    result['runtime']['reprocessed_without_page_ocr']=not bool(page_repairs)
    result['runtime']['original_extraction_elapsed_seconds']=result['runtime'].pop('elapsed_seconds',None)
    write_outputs(out,result,pages);save_json(out/'input_extraction.json',snapshot)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Extraction financière locale v3 : PDF natifs et scans, cellules et preuves.')
    parser.add_argument('pdf',type=Path,help='PDF ou dossier de PDF')
    parser.add_argument('-o','--output',type=Path,default=Path('extractions'))
    parser.add_argument('--jobs',type=int,default=2,help='Processus par document (défaut : 2)')
    parser.add_argument('--dpi',type=int,default=350,help='Résolution OCR, 150 à 600 (défaut : 350)')
    parser.add_argument('--ocr-language',default='fra+eng')
    parser.add_argument('--tesseract-cmd',default='tesseract',help='Chemin de tesseract.exe sous Windows si nécessaire')
    parser.add_argument('--ocr-timeout',type=int,default=60)
    parser.add_argument('--ocr',choices=['auto','always','never'],default='auto')
    parser.add_argument('--rotate',type=int,choices=[0,90,180,270],default=None,help='Rotation horaire imposée ; omettre pour automatique')
    parser.add_argument('--min-ocr-confidence',type=float,default=60)
    parser.add_argument('--no-cache',action='store_true')
    parser.add_argument('--pages',help='Exemple : 1-5,8 (numérotation à partir de 1)')
    parser.add_argument('--recursive',action='store_true')
    parser.add_argument('--strict',action='store_true',help='Code retour 2 si qualité incomplète ou problème détecté')
    parser.add_argument('--scan-backend',choices=['tesseract','docling'],default='tesseract')
    parser.add_argument('--liteparse-cmd',help='Optional lit executable used after a primary scan failure')
    parser.add_argument('--backend-timeout',type=int,default=180)
    parser.add_argument('--ollama-url',help='Optional Ollama endpoint; no model call when omitted')
    parser.add_argument('--max-llm-calls',type=int,default=4)
    parser.add_argument('--llm-timeout',type=int,default=30)
    parser.add_argument('--semantic-fallback',action='store_true')
    parser.add_argument('--repair-missing-pages',action='store_true',help='With --reprocess-json, retry at most two unresolved financial pages')
    parser.add_argument('--reprocess-json',type=Path,help='Reprocess a matching 3.1 physical-cell export without page OCR')
    parser.add_argument('--quiet',action='store_true')
    args = parser.parse_args()
    if args.repair_missing_pages and not args.reprocess_json:
        parser.error('--repair-missing-pages requires --reprocess-json')
    if args.reprocess_json and (args.pdf.is_dir() or args.pages):
        parser.error('--reprocess-json expects one matching PDF and its complete export, without --pages.')
    if args.max_llm_calls<0 or args.llm_timeout<1 or args.backend_timeout<1:
        parser.error("Budgets et délais invalides")
    if not 150 <= args.dpi <= 600 or args.jobs<1 or args.ocr_timeout<1 or not 0<=args.min_ocr_confidence<=100:
        parser.error('Vérifiez --dpi (150-600), --jobs (>=1), --ocr-timeout et --min-ocr-confidence (0-100).')
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,format='%(message)s')
    if args.pdf.is_dir():
        iterator = args.pdf.rglob('*') if args.recursive else args.pdf.iterdir()
        files = sorted(p for p in iterator if p.is_file() and p.suffix.lower()=='.pdf')
    else:
        files = [args.pdf]
    if not files:
        parser.error('Aucun PDF trouvé')
    try:
        pages = parse_pages(args.pages)
    except ValueError as exc:
        parser.error(str(exc))
    config = Config(dpi=args.dpi,ocr_language=args.ocr_language,tesseract_cmd=args.tesseract_cmd,
                    ocr_timeout=args.ocr_timeout,ocr=args.ocr,rotation=args.rotate,
                    min_ocr_confidence=args.min_ocr_confidence,cache=not args.no_cache,ollama_url=args.ollama_url,max_llm_calls=args.max_llm_calls,
                    llm_timeout=args.llm_timeout,semantic_fallback=args.semantic_fallback,scan_backend=args.scan_backend,
                    liteparse_cmd=args.liteparse_cmd,backend_timeout=args.backend_timeout)
    extractor = FinancialPDFExtractor(args.output,config,jobs=args.jobs)
    summaries = []
    for path in files:
        try:
            result = reprocess_extraction(args.reprocess_json,path,args.output,config,args.repair_missing_pages) if args.reprocess_json else extractor.extract(path,pages)
            summary = {'file':path.name,**result['quality'],'output_directory':result['output_directory']}
        except Exception as exc:
            LOG.error('%s : %s',path.name,exc)
            summary = {'file':path.name,'status':'error','error':type(exc).__name__+': '+str(exc)}
        summaries.append(summary)
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    args.output.mkdir(parents=True,exist_ok=True)
    save_json(args.output/'batch_summary.json',summaries)
    if any(s['status']=='error' for s in summaries):
        return 1
    return 2 if args.strict and any(s['status']!='checks_passed' for s in summaries) else 0


if __name__ == '__main__':
    raise SystemExit(main())
