# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "exports" / "mvp-fixtures" / "scenarios" / "_incoming_refs"
SCENARIOS = ROOT / "exports" / "mvp-fixtures" / "scenarios"

MAPPING = [
    ("01_business_center_linear_cornice.png", "business_center_linear_cornice"),
    ("02_administrative_horizontal_lines.png", "administrative_horizontal_lines"),
    ("03_shopping_center_vertical_lines.png", "shopping_center_vertical_lines"),
    ("04_small_office_projectors.png", "small_office_projectors"),
    ("05_historic_building_projectors.png", "historic_building_projectors"),
    ("06_residential_combined.png", "residential_combined"),
    ("07_hotel_combined.png", "hotel_combined"),
    ("08_restaurant_projectors_columns.png", "restaurant_projectors_columns"),
    ("09_industrial_building_vertical_wash.png", "industrial_vertical_wash"),
    ("10_warehouse_linear_contour.png", "warehouse_linear_contour"),
    ("11_car_showroom_linear_contour.png", "car_showroom_linear_contour"),
    ("12_sports_complex_projectors_wash.png", "sports_complex_projectors_wash"),
    ("13_theater_projectors_columns.png", "theater_projectors_columns"),
    ("14_university_combined.png", "university_combined"),
    ("15_church_projectors_architecture.png", "church_projectors_architecture"),
]


def main() -> None:
    for src_name, sid in MAPPING:
        src = INCOMING / src_name
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, SCENARIOS / f"{sid}.png")
        print("copied", sid)


if __name__ == "__main__":
    main()
