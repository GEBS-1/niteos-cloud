# -*- coding: utf-8 -*-
"""Import user reference images into assets/agent_references and build INDEX.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image

from vision_agent.reference_catalog import EXAMPLES_DIR, INDEX_PATH, REF_ROOT, THUMBS_DIR, ensure_ref_dirs

# Heuristic cluster assignment by rotating through style families for unlabeled imports.
# Specific UUID overrides for known reference sets from the Vision Agent Studio upload.
KNOWN_CLUSTER_HINTS: dict[str, str] = {
    # Contour / balcony ATLANT-like (from latest batch descriptions)
    "15b4d265": "linear_contour_balcony",
    "18108616": "linear_contour_balcony",
    "18930931": "linear_contour_balcony",
    "27cb4a64": "linear_contour_balcony",
    "2dec270d": "linear_contour_balcony",
    "2efa8f1f": "linear_contour_balcony",
    "320cad37": "linear_contour_balcony",
    "35cb6052": "linear_contour_balcony",
    "3979de7b": "linear_contour_balcony",
    "3b7341ba": "linear_contour_balcony",
    # Horizontal cornice bands
    "54a10e17": "linear_cornice_bands",
    "3c1e7461": "linear_cornice_bands",
    "b5f65ad7": "linear_cornice_bands",
    "e2a781d0": "linear_cornice_bands",
    "dc7f6b49": "linear_cornice_bands",
    "d12c20e2": "linear_cornice_bands",
    # Vertical up-down / classical
    "95237ebd": "vertical_updown_piers",
    "954fe84e": "vertical_updown_piers",
    "aa690eea": "vertical_updown_piers",
    "a0fcea68": "classical_heritage",
    "89332839": "classical_heritage",
    "c1915388": "classical_heritage",
    "8a5c0dda": "classical_heritage",
    "7891a13a": "classical_heritage",
    "e6242282": "classical_heritage",
    # Brick stagger wash
    "a47325eb": "vertical_wash_stagger",
    "672a7e22": "vertical_wash_stagger",
    "c2902268": "vertical_wash_stagger",
    "fe46e642": "vertical_wash_stagger",
    # Mixed commercial
    "899e6c15": "mixed_commercial",
    "be1b100f": "mixed_commercial",
    "bf22f5d4": "mixed_commercial",
    "062742ee": "mixed_commercial",
    "cc4697ad": "mixed_commercial",
    "80c43963": "portal_entrance",
    "f1a80651": "portal_entrance",
    "aaf876aa": "portal_entrance",
    "d64e09cf": "portal_entrance",
}

CLUSTER_DEFAULTS: dict[str, dict] = {
    "linear_contour_balcony": {
        "scenario_id": "residential_combined",
        "product_ids": ["magistral"],
        "placement_notes": "Continuous balcony-edge lines, no gaps at corners.",
    },
    "linear_cornice_bands": {
        "scenario_id": "business_center_linear_cornice",
        "product_ids": ["magistral"],
        "placement_notes": "Continuous cornice and floor belts.",
    },
    "vertical_updown_piers": {
        "scenario_id": "linear_cornice",
        "product_ids": ["xray"],
        "placement_notes": "Up-down cones on existing piers only.",
    },
    "vertical_wash_stagger": {
        "scenario_id": "xray_columns",
        "product_ids": ["xray"],
        "placement_notes": "Staggered vertical wash on masonry piers.",
    },
    "classical_heritage": {
        "scenario_id": "administrative_horizontal_lines",
        "product_ids": ["xray", "magistral"],
        "placement_notes": "Pilaster uplights + cornice crown.",
    },
    "mixed_commercial": {
        "scenario_id": "linear_mix_cv",
        "product_ids": ["magistral", "xray"],
        "placement_notes": "Contour + glazing glow + local accents.",
    },
    "portal_entrance": {
        "scenario_id": "historic_building_projectors",
        "product_ids": ["xray"],
        "placement_notes": "Entrance/portal accent without reshaping facade.",
    },
}

CLUSTER_ROTATION = list(CLUSTER_DEFAULTS.keys())

# Skip obvious UI screenshots / before-after garage daytime dumps if needed
SKIP_SUBSTRINGS = (
    "front-",
    "59be3551",  # UI screenshot
)


def _uuid_prefix(name: str) -> str:
    m = re.search(r"image-([0-9a-f]{8})", name.lower())
    return m.group(1) if m else ""


def _cluster_for(name: str, index: int) -> str:
    prefix = _uuid_prefix(name)
    if prefix and prefix in KNOWN_CLUSTER_HINTS:
        return KNOWN_CLUSTER_HINTS[prefix]
    return CLUSTER_ROTATION[index % len(CLUSTER_ROTATION)]


def _make_thumb(src: Path, dst: Path, max_side: int = 320) -> None:
    with Image.open(src) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, max_side / float(max(w, h)))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        img.save(dst, format="JPEG", quality=85)


def import_references(from_dir: Path, *, limit: int = 0, clear: bool = False) -> dict:
    ensure_ref_dirs()
    if clear and EXAMPLES_DIR.exists():
        for old in EXAMPLES_DIR.glob("*"):
            old.unlink(missing_ok=True)
        for old in THUMBS_DIR.glob("*"):
            old.unlink(missing_ok=True)

    src_dir = Path(from_dir)
    files = sorted(
        [p for p in src_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
        key=lambda p: p.name.lower(),
    )
    files = [p for p in files if p.name.lower().startswith("image-") or "image-" in p.name.lower()]
    files = [p for p in files if not any(s in p.name.lower() for s in SKIP_SUBSTRINGS)]
    if limit > 0:
        files = files[:limit]

    items: list[dict] = []
    for i, src in enumerate(files):
        digest = hashlib.sha1(src.name.encode("utf-8")).hexdigest()[:8]
        prefix = _uuid_prefix(src.name) or digest
        filename = f"ref_{i+1:02d}_{prefix}{src.suffix.lower()}"
        dst = EXAMPLES_DIR / filename
        shutil.copy2(src, dst)
        thumb = THUMBS_DIR / f"{Path(filename).stem}.jpg"
        try:
            _make_thumb(dst, thumb)
        except Exception:
            pass
        cluster = _cluster_for(src.name, i)
        defaults = CLUSTER_DEFAULTS[cluster]
        items.append({
            "id": f"aref_{i+1:02d}_{prefix}",
            "filename": filename,
            "thumb": thumb.name if thumb.exists() else "",
            "cluster": cluster,
            "title": f"{cluster} #{i+1}",
            "scenario_id": defaults["scenario_id"],
            "product_ids": list(defaults["product_ids"]),
            "placement_notes": defaults["placement_notes"],
            "source_name": src.name,
        })

    # Also seed a few mvp-fixtures if catalog is thin
    fixtures = ROOT_FIXTURES = Path(__file__).resolve().parent.parent / "exports" / "mvp-fixtures" / "scenarios"
    if fixtures.is_dir() and len(items) < 20:
        for png in sorted(fixtures.glob("*.png"))[:12]:
            cluster = "linear_cornice_bands"
            if "vertical" in png.stem or "projector" in png.stem or "xray" in png.stem:
                cluster = "vertical_updown_piers"
            if "residential" in png.stem:
                cluster = "linear_contour_balcony"
            if "historic" in png.stem or "church" in png.stem or "theater" in png.stem:
                cluster = "classical_heritage"
            defaults = CLUSTER_DEFAULTS[cluster]
            filename = f"fixture_{png.stem}.png"
            dst = EXAMPLES_DIR / filename
            if not dst.exists():
                shutil.copy2(png, dst)
            thumb = THUMBS_DIR / f"{Path(filename).stem}.jpg"
            try:
                _make_thumb(dst, thumb)
            except Exception:
                pass
            items.append({
                "id": f"fixture_{png.stem}",
                "filename": filename,
                "thumb": thumb.name if thumb.exists() else "",
                "cluster": cluster,
                "title": png.stem,
                "scenario_id": defaults["scenario_id"],
                "product_ids": list(defaults["product_ids"]),
                "placement_notes": defaults["placement_notes"],
                "source_name": png.name,
            })

    payload = {
        "version": 1,
        "count": len(items),
        "items": items,
    }
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(items), "index": str(INDEX_PATH), "examples_dir": str(EXAMPLES_DIR)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Vision Agent Studio references")
    parser.add_argument(
        "--from-dir",
        type=Path,
        default=Path(
            r"C:\Users\User\.cursor\projects\d-Python-Github-niteos-concept-light-v140-rgbw-neutral-fix\assets"
        ),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args(argv)
    summary = import_references(args.from_dir, limit=args.limit, clear=args.clear)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
