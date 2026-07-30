# -*- coding: utf-8 -*-
"""Vision Agent Studio: facade analysis, reference matching, chat-driven lighting."""

from __future__ import annotations

CLUSTER_STYLE_CONTRACTS: dict[str, str] = {
    "linear_contour_balcony": (
        "Continuous linear contour lighting along balcony/slab edges including every corner and zig-zag bend. "
        "No dark gaps between segments. Uniform warm or cool LED strip language. MAGISTRAL-style lines."
    ),
    "linear_cornice_bands": (
        "Continuous horizontal bands along cornices and floor belts on the full visible width. "
        "No broken lines at corners. Soft silhouette crown. MAGISTRAL horizontal language."
    ),
    "vertical_updown_piers": (
        "Narrow up-down projector cones only on EXISTING piers/prostenki between windows. "
        "Not solid vertical LED strips. Realistic falloff. X-RAY projector language."
    ),
    "vertical_wash_stagger": (
        "Warm vertical wall-wash accents on masonry piers in a staggered/tiered rhythm. "
        "Do not light every floor continuously; keep dark bands between tiers. X-RAY grazing."
    ),
    "classical_heritage": (
        "Uplights at bases of existing pilasters/columns plus cornice crown and portal accent. "
        "Preserve classical rhythm; do not invent new pilasters. Mix X-RAY + MAGISTRAL."
    ),
    "mixed_commercial": (
        "Contour on wings/cornices plus interior glow through glazing and local entrance accents. "
        "No street poles. Balanced commercial presentation look."
    ),
    "portal_entrance": (
        "Accent the entrance/portal/arch more brightly while keeping the rest of the facade coherent. "
        "Do not reshape the building."
    ),
}

CLUSTER_TO_SCHEME: dict[str, dict] = {
    "linear_contour_balcony": {
        "scenario_id": "residential_combined",
        "product_id": "magistral",
        "secondary_product_id": "",
    },
    "linear_cornice_bands": {
        "scenario_id": "business_center_linear_cornice",
        "product_id": "magistral",
        "secondary_product_id": "",
    },
    "vertical_updown_piers": {
        "scenario_id": "linear_cornice",
        "product_id": "xray",
        "secondary_product_id": "",
    },
    "vertical_wash_stagger": {
        "scenario_id": "xray_columns",
        "product_id": "xray",
        "secondary_product_id": "",
    },
    "classical_heritage": {
        "scenario_id": "administrative_horizontal_lines",
        "product_id": "xray",
        "secondary_product_id": "magistral",
    },
    "mixed_commercial": {
        "scenario_id": "linear_mix_cv",
        "product_id": "magistral",
        "secondary_product_id": "xray",
    },
    "portal_entrance": {
        "scenario_id": "historic_building_projectors",
        "product_id": "xray",
        "secondary_product_id": "",
    },
}

__all__ = [
    "CLUSTER_STYLE_CONTRACTS",
    "CLUSTER_TO_SCHEME",
]
