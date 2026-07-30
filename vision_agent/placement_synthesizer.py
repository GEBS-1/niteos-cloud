# -*- coding: utf-8 -*-
"""Synthesize placement plan + studio render prompt."""
from __future__ import annotations

from vision_agent import CLUSTER_STYLE_CONTRACTS


def synthesize_placement_plan(
    *,
    analysis: dict,
    scheme: dict,
    matched_refs: list[dict],
) -> dict:
    cluster = scheme.get("cluster") or "linear_cornice_bands"
    continuous = cluster in {
        "linear_contour_balcony",
        "linear_cornice_bands",
        "mixed_commercial",
        "classical_heritage",
    }
    vertical = cluster in {
        "vertical_updown_piers",
        "vertical_wash_stagger",
        "classical_heritage",
        "portal_entrance",
    }
    return {
        "cluster": cluster,
        "forbidden_gaps": True,
        "continuous_lines": continuous,
        "vertical_accents": vertical,
        "cover_full_facade": True,
        "preserve_signs": True,
        "no_new_pilasters": True,
        "building_type": analysis.get("building_type"),
        "scenario_id": scheme.get("scenario_id"),
        "product_id": scheme.get("product_id"),
        "reference_ids": [r.get("id") for r in matched_refs if r.get("id")],
        "rules": [
            "No dark gaps where the same lighting rhythm should continue.",
            "Light only on existing architectural members.",
            "Do not invent pilasters, columns, or decorative plaques.",
            "Preserve signs, cameras, stickers from source photo.",
            "Image 1 architecture identity is mandatory; references are lighting LOOK only.",
        ],
        "style_contract": scheme.get("style_contract")
        or CLUSTER_STYLE_CONTRACTS.get(cluster, ""),
        "placement_notes": scheme.get("placement_notes") or "",
    }


def build_studio_render_prompt(
    *,
    scenario_prompt: str,
    placement_plan: dict,
    scheme: dict,
    analysis: dict,
    user_delta: str = "",
) -> str:
    contract = placement_plan.get("style_contract") or scheme.get("style_contract") or ""
    notes = placement_plan.get("placement_notes") or scheme.get("placement_notes") or ""
    parts = [
        "NITEOS Vision Agent Studio - architectural facade lighting render.",
        "IMAGE ORDER:",
        "1) Source facade - keep geometry, materials, windows, signs 1:1.",
        "2) Lighting look reference - transfer light rhythm/intensity only, never architecture.",
        "3) Optional light-map overlay - place light along marked zones; do not keep overlay graphics in final.",
        "",
        (scenario_prompt or "").strip(),
        "",
        "STYLE CONTRACT (mandatory):",
        contract,
        f"Placement notes: {notes}" if notes else "",
        "NO GAPS: continuous rhythms must not break at corners, bends, or mid-bays where the scheme continues.",
        "Do not add street poles. Facade architectural lighting only.",
        f"Facade analysis: type={analysis.get('building_type')}, "
        f"balconies={analysis.get('has_balconies')}, pilasters={analysis.get('has_pilasters')}, "
        f"glass={analysis.get('has_glass')}, classical={analysis.get('is_classical')}.",
    ]
    if user_delta.strip():
        parts.extend(["", "USER REVISION REQUEST:", user_delta.strip()])
    return "\n".join(p for p in parts if p is not None)
