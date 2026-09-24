"""Configuration runtime des sources sectorielles (persistée, modifiable depuis le front).

Le défaut global ne réécrit jamais les dossiers déjà épinglés.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.sector.sources_catalog import (
    DEFAULT_SOURCE_ID,
    SECTOR_SOURCES,
    get_source,
    resolve_source_id,
)

_lock = threading.Lock()
_cache: dict[str, Any] | None = None


def _config_path() -> Path:
    base = settings.dossiers_store_path
    path = Path(base)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.parent / "sector_sources_config.json"


def _default_payload() -> dict[str, Any]:
    # Honore SECTOR_DATA_PROVIDER / SECTOR_PROVIDER comme défaut initial une seule fois.
    env_default = resolve_source_id(settings.sector_data_provider, DEFAULT_SOURCE_ID)
    if not get_source(env_default) or not get_source(env_default).supports_va_analysis:
        env_default = DEFAULT_SOURCE_ID
    return {
        "defaultSourceId": env_default,
        "sources": {
            sid: {
                "enabled": src.default_enabled,
                "selectable": src.default_enabled and src.supports_va_analysis,
            }
            for sid, src in SECTOR_SOURCES.items()
        },
        "updatedAt": None,
        "updatedBy": None,
    }


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    path = _config_path()
    payload = _default_payload()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload["defaultSourceId"] = resolve_source_id(
                    raw.get("defaultSourceId"), payload["defaultSourceId"]
                )
                incoming = raw.get("sources") or {}
                if isinstance(incoming, dict):
                    for sid, src in SECTOR_SOURCES.items():
                        item = incoming.get(sid) or {}
                        payload["sources"][sid] = {
                            "enabled": bool(item.get("enabled", src.default_enabled)),
                            "selectable": bool(
                                item.get(
                                    "selectable",
                                    src.default_enabled and src.supports_va_analysis,
                                )
                            ),
                        }
                payload["updatedAt"] = raw.get("updatedAt")
                payload["updatedBy"] = raw.get("updatedBy")
        except Exception:
            pass
    _cache = payload
    return payload


def _save(payload: dict[str, Any]) -> None:
    global _cache
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache = payload


def get_config() -> dict[str, Any]:
    with _lock:
        return dict(_load())


def get_default_source_id() -> str:
    with _lock:
        return resolve_source_id(_load().get("defaultSourceId"), DEFAULT_SOURCE_ID)


def is_source_enabled(source_id: str) -> bool:
    sid = resolve_source_id(source_id)
    with _lock:
        item = (_load().get("sources") or {}).get(sid) or {}
    return bool(item.get("enabled", False))


def is_source_selectable(source_id: str) -> bool:
    sid = resolve_source_id(source_id)
    src = get_source(sid)
    if src is None:
        return False
    with _lock:
        item = (_load().get("sources") or {}).get(sid) or {}
    # Jamais sélectionnable pour l'analyse VA si non implémenté.
    if not src.supports_va_analysis:
        return False
    return bool(item.get("enabled", False)) and bool(item.get("selectable", False))


def set_default_source(source_id: str, *, actor: str | None = None) -> dict[str, Any]:
    sid = resolve_source_id(source_id)
    src = get_source(sid)
    if src is None:
        raise ValueError("Source inconnue")
    if not src.supports_va_analysis:
        raise ValueError(
            f"La source « {src.short_label} » ne peut pas être le défaut : "
            "analyse VA non supportée pour le moment."
        )
    with _lock:
        payload = dict(_load())
        sources = dict(payload.get("sources") or {})
        entry = dict(sources.get(sid) or {})
        entry["enabled"] = True
        entry["selectable"] = True
        sources[sid] = entry
        payload["sources"] = sources
        payload["defaultSourceId"] = sid
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        payload["updatedBy"] = actor or "analyste"
        _save(payload)
        return dict(payload)


def update_source_flags(
    source_id: str,
    *,
    enabled: bool | None = None,
    selectable: bool | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    sid = resolve_source_id(source_id)
    src = get_source(sid)
    if src is None:
        raise ValueError("Source inconnue")
    with _lock:
        payload = dict(_load())
        sources = dict(payload.get("sources") or {})
        entry = dict(sources.get(sid) or {"enabled": False, "selectable": False})
        if enabled is not None:
            entry["enabled"] = bool(enabled)
        if selectable is not None:
            # Bloque la sélection VA pour les sources non prêtes.
            if bool(selectable) and not src.supports_va_analysis:
                raise ValueError(
                    f"« {src.short_label} » n’est pas encore prête pour l’analyse sectorielle VA."
                )
            entry["selectable"] = bool(selectable) and src.supports_va_analysis
        if not entry["enabled"]:
            entry["selectable"] = False
            if payload.get("defaultSourceId") == sid:
                # Bascule le défaut vers HCP si on désactive la source par défaut.
                payload["defaultSourceId"] = DEFAULT_SOURCE_ID
                hcp = dict(sources.get(DEFAULT_SOURCE_ID) or {})
                hcp["enabled"] = True
                hcp["selectable"] = True
                sources[DEFAULT_SOURCE_ID] = hcp
        sources[sid] = entry
        payload["sources"] = sources
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        payload["updatedBy"] = actor or "analyste"
        _save(payload)
        return dict(payload)


def list_sources_for_api(*, status_by_code: dict[str, dict] | None = None) -> dict[str, Any]:
    """Vue catalogue + config + statut sync pour le panneau frontend."""
    cfg = get_config()
    default_id = resolve_source_id(cfg.get("defaultSourceId"), DEFAULT_SOURCE_ID)
    items = []
    for sid, src in SECTOR_SOURCES.items():
        flags = (cfg.get("sources") or {}).get(sid) or {}
        sync = (status_by_code or {}).get(src.code) or (status_by_code or {}).get(sid) or {}
        items.append(
            {
                "id": src.id,
                "code": src.code,
                "label": src.label,
                "shortLabel": src.short_label,
                "providerType": src.provider_type,
                "description": src.description,
                "capabilities": list(src.capabilities),
                "supportsVaAnalysis": src.supports_va_analysis,
                "implemented": src.implemented,
                "enabled": bool(flags.get("enabled", src.default_enabled)),
                "selectable": bool(flags.get("selectable", False)) and src.supports_va_analysis,
                "isDefault": sid == default_id,
                "notes": src.notes,
                "branchCatalog": src.branch_catalog,
                "datasetRoles": dict(src.dataset_roles),
                "syncStatus": sync.get("status"),
                "lastSyncAt": sync.get("lastUpdatedAt") or sync.get("lastCheckedAt"),
            }
        )
    return {
        "defaultSourceId": default_id,
        "items": items,
        "updatedAt": cfg.get("updatedAt"),
        "updatedBy": cfg.get("updatedBy"),
        "rules": {
            "perDossierPin": True,
            "clearMappingOnSourceChange": True,
            "codeNamespacesIsolated": True,
            "globalDefaultNeverOverridesPinned": True,
        },
    }
