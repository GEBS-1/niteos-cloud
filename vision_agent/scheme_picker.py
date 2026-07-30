# -*- coding: utf-8 -*-
"""Map matched reference cluster to catalog scenario + products."""
from __future__ import annotations

from vision_agent import CLUSTER_STYLE_CONTRACTS, CLUSTER_TO_SCHEME


def pick_scheme_and_product(matched_refs: list[dict], analysis: dict | None = None) -> dict:
    primary = matched_refs[0] if matched_refs else {}
    cluster = str(primary.get("cluster") or "")
    if not cluster and analysis:
        suggested = analysis.get("suggested_clusters") or []
        cluster = str(suggested[0]) if suggested else "linear_cornice_bands"
    mapping = CLUSTER_TO_SCHEME.get(cluster) or CLUSTER_TO_SCHEME["linear_cornice_bands"]
    scenario_id = primary.get("scenario_id") or mapping["scenario_id"]
    product_ids = list(primary.get("product_ids") or [])
    product_id = product_ids[0] if product_ids else mapping["product_id"]
    secondary_product_id = (
        product_ids[1] if len(product_ids) > 1 else mapping.get("secondary_product_id") or ""
    )
    return {
        "cluster": cluster,
        "scenario_id": scenario_id,
        "product_id": product_id,
        "secondary_product_id": secondary_product_id,
        "style_contract": CLUSTER_STYLE_CONTRACTS.get(cluster, CLUSTER_STYLE_CONTRACTS["linear_cornice_bands"]),
        "placement_notes": primary.get("placement_notes") or "",
        "reference_id": primary.get("id") or "",
        "reference_title": primary.get("title") or "",
    }
