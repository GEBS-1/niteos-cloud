# -*- coding: utf-8 -*-
"""Strip diagonal niteos.ru watermark before putting targets into train set."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def strip_niteos_watermark(src: Path, dst: Path, max_side: int = 2048) -> Path:
    """
    Soften center-diagonal watermark region so LoRA does not learn niteos.ru.
    Not perfect inpaint - reduces text imprint for style training.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as opened:
        img = opened.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            w, h = img.size
        blurred = img.filter(ImageFilter.GaussianBlur(radius=max(2, min(w, h) // 120)))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        thickness = max(24, int(min(w, h) * 0.12))
        for offset in range(-thickness // 2, thickness // 2 + 1, 2):
            draw.line([(0 + offset, 0), (w + offset, h)], fill=255, width=3)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, thickness // 3)))
        out = Image.composite(blurred, img, mask)
        out.save(dst, format="PNG", optimize=True)
    return dst
