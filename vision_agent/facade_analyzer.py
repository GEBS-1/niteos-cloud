# -*- coding: utf-8 -*-
"""Facade analysis for Vision Agent Studio."""
from __future__ import annotations

from pathlib import Path
from typing import Callable


def analyze_facade_for_studio(
    base: Path,
    *,
    analyze_facade_source: Callable,
    prepare_image_for_vision: Callable,
    call_routerai_vision_json: Callable,
    classifier_model: str = "",
) -> tuple[dict, dict]:
    """Combine local heuristics with optional vision JSON."""
    facade = analyze_facade_source(base)
    source = base / "input" / "building.png"
    analysis = {
        "facade": facade,
        "building_type": "unknown",
        "has_balconies": False,
        "has_pilasters": False,
        "has_glass": False,
        "is_classical": False,
        "is_modern": False,
        "suggested_clusters": [],
        "vision": {},
        "reason": "local heuristics only",
    }
    tags = [str(t).lower() for t in (facade.get("tags") or [])]
    composition = str(facade.get("composition") or "").lower()
    if any(t in tags for t in ("glass", "modern", "curtain")) or "glass" in composition:
        analysis["has_glass"] = True
        analysis["is_modern"] = True
    if any(t in tags for t in ("classic", "masonry", "stone", "brick")):
        analysis["is_classical"] = True
    if facade.get("aspect", 1) and float(facade.get("aspect") or 1) > 1.4:
        analysis["building_type"] = "wide_wing"
    elif float(facade.get("aspect") or 1) < 0.75:
        analysis["building_type"] = "tower"
    else:
        analysis["building_type"] = "midrise"

    # Suggested clusters from heuristics
    suggested = []
    if analysis["is_classical"]:
        suggested.extend(["classical_heritage", "vertical_updown_piers"])
    if analysis["is_modern"] or analysis["has_glass"]:
        suggested.extend(["linear_cornice_bands", "mixed_commercial"])
    if analysis["building_type"] == "tower":
        suggested.append("vertical_wash_stagger")
    if not suggested:
        suggested = ["linear_cornice_bands", "vertical_updown_piers", "mixed_commercial"]
    analysis["suggested_clusters"] = list(dict.fromkeys(suggested))

    api_log: dict = {"skipped": True, "reason": "no_vision"}
    if not source.exists():
        return analysis, api_log

    prompt = (
        "You are an architectural lighting analyst for NITEOS Vision Agent Studio.\n"
        "Analyze the facade photo and return JSON only:\n"
        "{\n"
        '  "building_type": "classic_palace|modern_tower|residential_balconies|office_glass|retail_mixed|industrial|other",\n'
        '  "has_balconies": true,\n'
        '  "has_pilasters": true,\n'
        '  "has_glass": true,\n'
        '  "is_classical": true,\n'
        '  "is_modern": true,\n'
        '  "suggested_clusters": ["linear_contour_balcony"|"linear_cornice_bands"|"vertical_updown_piers"|"vertical_wash_stagger"|"classical_heritage"|"mixed_commercial"|"portal_entrance"],\n'
        '  "reason": "1-2 sentences"\n'
        "}\n"
        "Prefer clusters that match real geometry. Do not invent features.\n"
        f"Local heuristics: {facade}"
    )
    try:
        vision_path = prepare_image_for_vision(source, max_side=1600)
        result, api_log = call_routerai_vision_json(prompt, [vision_path], model=classifier_model)
        api_log["kind"] = "studio_facade_analyze"
        if isinstance(result, dict):
            analysis["vision"] = result
            for key in (
                "building_type", "has_balconies", "has_pilasters", "has_glass",
                "is_classical", "is_modern", "reason",
            ):
                if key in result and result[key] not in (None, ""):
                    analysis[key] = result[key]
            clusters = result.get("suggested_clusters") or []
            if isinstance(clusters, list) and clusters:
                analysis["suggested_clusters"] = [str(c) for c in clusters][:5]
    except Exception as exc:
        api_log = {"skipped": False, "error": str(exc), "kind": "studio_facade_analyze"}
    return analysis, api_log
