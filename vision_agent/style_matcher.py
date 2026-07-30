# -*- coding: utf-8 -*-
"""Match facade analysis to agent reference library."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from vision_agent.reference_catalog import load_reference_index, reference_path


def match_references(
    analysis: dict,
    *,
    prepare_image_for_vision: Callable | None = None,
    call_routerai_vision_json: Callable | None = None,
    source_path: Path | None = None,
    classifier_model: str = "",
    limit: int = 2,
) -> tuple[list[dict], dict]:
    """
    Rank references: prefer suggested clusters; optionally ask vision to pick among candidates.
    Returns list of catalog items (primary first) + api_log.
    """
    catalog = load_reference_index()
    if not catalog:
        return [], {"error": "empty_reference_catalog"}

    suggested = [str(c) for c in (analysis.get("suggested_clusters") or [])]
    scored: list[tuple[float, dict]] = []
    for item in catalog:
        score = 0.0
        cluster = str(item.get("cluster") or "")
        if cluster in suggested:
            score += 3.0 + max(0, 2 - suggested.index(cluster))
        if analysis.get("has_balconies") and cluster == "linear_contour_balcony":
            score += 2.0
        if analysis.get("is_classical") and cluster in {"classical_heritage", "vertical_updown_piers"}:
            score += 1.5
        if analysis.get("is_modern") and cluster in {"linear_cornice_bands", "mixed_commercial"}:
            score += 1.5
        if analysis.get("has_glass") and cluster == "mixed_commercial":
            score += 1.0
        if reference_path(item):
            score += 0.1
        scored.append((score, item))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id"))))
    top = [item for _, item in scored[: max(8, limit)]]

    api_log: dict = {"method": "heuristic", "candidates": [i.get("id") for i in top]}
    # Vision re-rank among top candidates if available
    if (
        source_path
        and source_path.exists()
        and prepare_image_for_vision
        and call_routerai_vision_json
        and len(top) >= 2
    ):
        ids = [str(i.get("id")) for i in top[:8]]
        prompt = (
            "Pick the best lighting LOOK reference for the source facade (Image 1).\n"
            "Candidate reference ids and clusters:\n"
            + "\n".join(
                f"- {i.get('id')}: cluster={i.get('cluster')}, notes={i.get('placement_notes')}"
                for i in top[:8]
            )
            + "\nReturn JSON only: {\"primary_id\": \"...\", \"secondary_id\": \"...\", \"reason\": \"...\"}\n"
            "primary_id must be one of the listed ids. Prefer continuous full-facade lighting language."
        )
        try:
            images = [prepare_image_for_vision(source_path, max_side=1400)]
            # Attach up to 3 candidate images
            for item in top[:3]:
                path = reference_path(item)
                if path:
                    images.append(prepare_image_for_vision(path, max_side=900))
            result, api_log = call_routerai_vision_json(prompt, images, model=classifier_model)
            api_log["kind"] = "studio_style_match"
            api_log["method"] = "vision"
            by_id = {str(i.get("id")): i for i in catalog}
            primary = by_id.get(str(result.get("primary_id") or ""))
            secondary = by_id.get(str(result.get("secondary_id") or ""))
            picked = []
            if primary:
                picked.append(primary)
            if secondary and secondary is not primary:
                picked.append(secondary)
            for item in top:
                if item not in picked:
                    picked.append(item)
                if len(picked) >= limit:
                    break
            return picked[:limit], api_log
        except Exception as exc:
            api_log = {"method": "heuristic_fallback", "error": str(exc), "candidates": ids}

    return [item for item in top[:limit]], api_log
