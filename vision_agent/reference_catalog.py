# -*- coding: utf-8 -*-
"""Reference catalog for Vision Agent Studio."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_ROOT = ROOT / "assets" / "agent_references"
EXAMPLES_DIR = REF_ROOT / "examples"
THUMBS_DIR = REF_ROOT / "thumbs"
INDEX_PATH = REF_ROOT / "INDEX.json"


def ensure_ref_dirs() -> None:
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def load_reference_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        items = data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    return [item for item in items if isinstance(item, dict) and item.get("id")]


def reload_reference_index() -> list[dict]:
    load_reference_index.cache_clear()
    return load_reference_index()


def reference_path(item: dict) -> Path | None:
    filename = str(item.get("filename") or item.get("image") or "")
    if not filename:
        return None
    path = EXAMPLES_DIR / filename
    return path if path.exists() else None


def list_references_public() -> list[dict]:
    out = []
    for item in load_reference_index():
        path = reference_path(item)
        out.append({
            "id": item.get("id"),
            "cluster": item.get("cluster"),
            "title": item.get("title") or item.get("id"),
            "scenario_id": item.get("scenario_id"),
            "product_ids": item.get("product_ids") or [],
            "placement_notes": item.get("placement_notes") or "",
            "filename": item.get("filename"),
            "has_file": bool(path),
            "url": f"/api/studio/references/{item.get('id')}/file" if path else "",
            "thumb_url": f"/api/studio/references/{item.get('id')}/thumb" if path else "",
        })
    return out


def get_reference_by_id(ref_id: str) -> dict | None:
    for item in load_reference_index():
        if item.get("id") == ref_id:
            return item
    return None


def references_by_cluster(cluster: str) -> list[dict]:
    return [item for item in load_reference_index() if item.get("cluster") == cluster]
