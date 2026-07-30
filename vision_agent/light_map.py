# -*- coding: utf-8 -*-
"""Simple light-map overlay hint for continuous lighting zones."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def generate_agent_light_map(
    source_path: Path,
    out_path: Path,
    placement_plan: dict,
) -> Path | None:
    """Draw soft guide lines on a darkened copy of the facade as a model hint."""
    if not source_path.exists():
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as src:
        img = src.convert("RGBA")
        w, h = img.size
        max_side = 1600
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            w, h = img.size
        # Darken
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 110))
        base = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(base, "RGBA")
        color = (245, 185, 66, 200)
        if placement_plan.get("continuous_lines"):
            # Horizontal bands: cornice + mid + base
            for y_ratio in (0.12, 0.38, 0.62, 0.88):
                y = int(h * y_ratio)
                draw.line([(int(w * 0.05), y), (int(w * 0.95), y)], fill=color, width=max(2, w // 280))
        if placement_plan.get("vertical_accents"):
            for x_ratio in (0.15, 0.30, 0.45, 0.60, 0.75, 0.88):
                x = int(w * x_ratio)
                draw.line([(x, int(h * 0.08)), (x, int(h * 0.92))], fill=(120, 180, 255, 160), width=max(2, w // 320))
        rgb = base.convert("RGB")
        rgb.save(out_path, format="PNG", optimize=True)
    return out_path if out_path.exists() else None
