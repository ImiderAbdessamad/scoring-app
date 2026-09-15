from __future__ import annotations

import re
import unicodedata

from app.sector.domain import SectorMappingResult

# Branches HCP observées dans data_12_29 (labels officiels).
HCP_BRANCHES: dict[str, str] = {
    "HCP_AGRICULTURE": "Agriculture et sylviculture",
    "HCP_PECHE": "Pêche et aquaculture",
    "HCP_EXTRACTION": "Extraction",
    "HCP_MANUFACTURIER": "Industries manufacturières",
    "HCP_ALIMENTAIRE": "Fabrication de produits alimentaires et de boissons et tabacs",
    "HCP_TEXTILE": "Fabrication de textiles, d’articles d’habillement, de cuir et d’articles de cuir",
    "HCP_BOIS_PAPIER": "Fabrication d’articles en bois et en papier; imprimerie et reproduction de supports",
    "HCP_COKE_RAFFINAGE": "Cokéfaction et raffinage",
    "HCP_CHIMIE": "Fabrication de produits chimiques",
    "HCP_PHARMA": "Fabrication de produits pharmaceutiques de base et de préparations pharmaceutiques",
    "HCP_CAOUTCHOUC": "Fabrication d’articles en caoutchouc et en matières plastiques, et autres produits minéraux non métalliques",
    "HCP_METALLURGIE": "Fabrication de produits métallurgiques de base et d’ouvrages en métaux, sauf machines et matériel",
    "HCP_ELECTRONIQUE": "Fabrication d’ordinateurs, d’articles électroniques et optiques",
    "HCP_EQUIPEMENTS_ELECTRIQUES": "Fabrication d'équipements électriques",
    "HCP_MACHINES": "Fabrication de machines et de matériel, n.c.a",
    "HCP_MATERIEL_TRANSPORT": "Fabrication de matériel de transport",
    "HCP_AUTRES_FAB": "Autres activités de fabrication (y.c fabrication de meubles), réparation et installation",
    "HCP_ENERGIE_EAU": "Distribution d’électricité et de gaz-Distribution d’eau, réseau d’assainissement, traitement des déchets",
    "HCP_CONSTRUCTION": "Construction",
    "HCP_COMMERCE": "Commerce de gros et de détail; réparation de véhicules automobiles et de motocycles",
    "HCP_TRANSPORTS": "Transports et entreposage",
    "HCP_HEBERGEMENT": "Activités d’hébergement et de restauration",
    "HCP_INFORMATION": "Information et communication",
    "HCP_FINANCE": "Activités financières et d'assurance",
    "HCP_IMMOBILIER": "Activités immobilières",
    "HCP_SERVICES_ENTREPRISES": "Recherches et développement et services rendus aux entreprises",
    "HCP_ADMIN": "Administration publique; sécurité sociale obligatoire",
    "HCP_EDUCATION_SANTE": "Education, santé humaine et activités d’action sociale",
    "HCP_AUTRES_SERVICES": "Autres services",
}

_ALIASES: dict[str, str] = {
    "construction": "HCP_CONSTRUCTION",
    "btp": "HCP_CONSTRUCTION",
    "batiment": "HCP_CONSTRUCTION",
    "travaux publics": "HCP_CONSTRUCTION",
    "commerce": "HCP_COMMERCE",
    "commerce de gros": "HCP_COMMERCE",
    "commerce de detail": "HCP_COMMERCE",
    "industrie manufacturiere": "HCP_MANUFACTURIER",
    "industries manufacturieres": "HCP_MANUFACTURIER",
    "agriculture": "HCP_AGRICULTURE",
    "immobilier": "HCP_IMMOBILIER",
    "activites immobilieres": "HCP_IMMOBILIER",
    "transport": "HCP_TRANSPORTS",
    "transports": "HCP_TRANSPORTS",
    "transports et entreposage": "HCP_TRANSPORTS",
    "logistique": "HCP_TRANSPORTS",
    "hotellerie": "HCP_HEBERGEMENT",
    "restauration": "HCP_HEBERGEMENT",
    "hebergement": "HCP_HEBERGEMENT",
    "banque": "HCP_FINANCE",
    "assurance": "HCP_FINANCE",
    "finance": "HCP_FINANCE",
    "telecommunication": "HCP_INFORMATION",
    "telecom": "HCP_INFORMATION",
    "information et communication": "HCP_INFORMATION",
    "pharmacie": "HCP_PHARMA",
    "pharmaceutique": "HCP_PHARMA",
    "chimie": "HCP_CHIMIE",
    "chimique": "HCP_CHIMIE",
    "textile": "HCP_TEXTILE",
    "habillement": "HCP_TEXTILE",
    "extraction": "HCP_EXTRACTION",
    "mines": "HCP_EXTRACTION",
    "peche": "HCP_PECHE",
    "education": "HCP_EDUCATION_SANTE",
    "sante": "HCP_EDUCATION_SANTE",
}

_KEYWORDS: list[tuple[str, str]] = [
    ("cables electriques", "HCP_EQUIPEMENTS_ELECTRIQUES"),
    ("equipements electriques", "HCP_EQUIPEMENTS_ELECTRIQUES"),
    ("materiel de transport", "HCP_MATERIEL_TRANSPORT"),
    ("automobile", "HCP_MATERIEL_TRANSPORT"),
    ("pharmaceut", "HCP_PHARMA"),
    ("chimique", "HCP_CHIMIE"),
    ("textile", "HCP_TEXTILE"),
    ("habillement", "HCP_TEXTILE"),
    ("construction", "HCP_CONSTRUCTION"),
    ("batiment", "HCP_CONSTRUCTION"),
    ("btp", "HCP_CONSTRUCTION"),
    ("commerce", "HCP_COMMERCE"),
    ("vehicules", "HCP_COMMERCE"),
    ("gros et detail", "HCP_COMMERCE"),
    ("agriculture", "HCP_AGRICULTURE"),
    ("sylviculture", "HCP_AGRICULTURE"),
    ("peche", "HCP_PECHE"),
    ("extraction", "HCP_EXTRACTION"),
    ("phosphate", "HCP_EXTRACTION"),
    ("manufactur", "HCP_MANUFACTURIER"),
    ("hebergement", "HCP_HEBERGEMENT"),
    ("restauration", "HCP_HEBERGEMENT"),
    ("hotel", "HCP_HEBERGEMENT"),
    ("entreposage", "HCP_TRANSPORTS"),
    ("transport", "HCP_TRANSPORTS"),
    ("logistique", "HCP_TRANSPORTS"),
    ("immobilier", "HCP_IMMOBILIER"),
    ("assurance", "HCP_FINANCE"),
    ("bancaire", "HCP_FINANCE"),
    ("telecom", "HCP_INFORMATION"),
    ("communication", "HCP_INFORMATION"),
    ("electricite", "HCP_ENERGIE_EAU"),
    ("assainissement", "HCP_ENERGIE_EAU"),
    ("education", "HCP_EDUCATION_SANTE"),
    ("sante", "HCP_EDUCATION_SANTE"),
    ("services aux entreprises", "HCP_SERVICES_ENTREPRISES"),
]

MATCH_THRESHOLD = 0.75


def normalize_activity(text: str | None) -> str:
    if not text:
        return ""
    folded = unicodedata.normalize("NFD", text)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    folded = folded.lower().replace("œ", "oe")
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def slug_sector_label(label: str) -> str:
    norm = normalize_activity(label).replace(" ", "_")
    return "HCP_" + (norm.upper()[:80] or "UNKNOWN")


def is_plausible_activity(text: str | None) -> bool:
    normalized = normalize_activity(text)
    if not normalized or len(normalized) < 3:
        return False
    junk_prefixes = (
        "raison sociale",
        "denomination",
        "identifiant fiscal",
        "identifiant commun",
        "ice",
        "rc ",
        "n rc",
    )
    return not any(normalized.startswith(prefix) for prefix in junk_prefixes)


def resolve_mapping(*candidates: str | None) -> SectorMappingResult:
    """Essaie chaque candidat ; ne s’arrête pas sur un libellé OCR parasite."""
    best: SectorMappingResult | None = None
    for raw in candidates:
        if not is_plausible_activity(raw):
            continue
        mapped = map_activity(raw)
        if mapped.status == "MATCHED":
            return mapped
        if best is None or mapped.confidence > best.confidence:
            best = mapped
    return best or map_activity(None)


def map_activity(*candidates: str | None) -> SectorMappingResult:
    raw = next((c for c in candidates if c and str(c).strip()), None)
    normalized = normalize_activity(raw)
    if not normalized:
        return SectorMappingResult(raw_activity=raw, normalized_activity=normalized, status="UNMATCHED")

    for code, label in HCP_BRANCHES.items():
        if normalized == normalize_activity(label):
            return SectorMappingResult(
                raw_activity=raw,
                normalized_activity=normalized,
                sector_code=code,
                sector_label=label,
                confidence=1.0,
                status="MATCHED",
                mapping_method="EXACT",
            )

    if normalized in _ALIASES:
        code = _ALIASES[normalized]
        return SectorMappingResult(
            raw_activity=raw,
            normalized_activity=normalized,
            sector_code=code,
            sector_label=HCP_BRANCHES[code],
            confidence=0.95,
            status="MATCHED",
            mapping_method="ALIAS",
        )

    hits: dict[str, str] = {}
    for keyword, code in _KEYWORDS:
        if keyword in normalized:
            hits[code] = keyword
    if len(hits) == 1:
        code = next(iter(hits))
        confidence = 0.82
        status = "MATCHED" if confidence >= MATCH_THRESHOLD else "REVIEW_REQUIRED"
        return SectorMappingResult(
            raw_activity=raw,
            normalized_activity=normalized,
            sector_code=code,
            sector_label=HCP_BRANCHES[code],
            confidence=confidence,
            status=status,
            mapping_method="KEYWORD",
        )
    if len(hits) > 1:
        code = next(iter(hits))
        return SectorMappingResult(
            raw_activity=raw,
            normalized_activity=normalized,
            sector_code=None,
            sector_label=None,
            confidence=0.4,
            status="REVIEW_REQUIRED",
            mapping_method="KEYWORD",
        )
    return SectorMappingResult(
        raw_activity=raw,
        normalized_activity=normalized,
        status="UNMATCHED",
        confidence=0.0,
    )


def mapping_from_hcp_code(code: str, raw: str | None = None) -> SectorMappingResult | None:
    if code not in HCP_BRANCHES:
        return None
    return SectorMappingResult(
        raw_activity=raw,
        normalized_activity=normalize_activity(raw) or normalize_activity(HCP_BRANCHES[code]),
        sector_code=code,
        sector_label=HCP_BRANCHES[code],
        confidence=1.0,
        status="MATCHED",
        mapping_method="MANUAL",
        validated=True,
    )


def resolve_mapping_for_record(record, identity=None) -> SectorMappingResult:
    code = getattr(record, "benchmarkSectorCode", None)
    raw = getattr(record, "sectorRaw", None) or getattr(record, "sector", None)
    manual = mapping_from_hcp_code(str(code), raw) if code else None
    if manual is not None:
        return manual
    return resolve_mapping(
        getattr(record, "sectorRaw", None),
        getattr(record, "sector", None),
        getattr(record, "sectorNormalized", None),
        getattr(identity, "secteur", None) if identity else None,
        getattr(identity, "activite", None) if identity else None,
    )
