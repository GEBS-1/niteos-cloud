#!/usr/bin/env python3
"""Batch-test auto scenario classification on assets/viz_examples/examples."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cloud_app import (  # noqa: E402
    VIZ_EXAMPLES_DIR,
    classify_scenario_from_facade,
    ensure_project_dirs,
    list_auto_test_photos,
    save_rgb,
)


def main() -> int:
    photos = list_auto_test_photos()
    if not photos:
        print("No photos in", VIZ_EXAMPLES_DIR)
        return 1
    out_path = ROOT / "assets" / "viz_examples" / "auto_test_results.json"
    results = []
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(photos)
    for item in photos[:limit]:
        src = VIZ_EXAMPLES_DIR / item["filename"]
        print("CLASSIFY", item["filename"], flush=True)
        with tempfile.TemporaryDirectory(prefix="niteos_auto_test_") as tmp:
            base = Path(tmp) / "project"
            ensure_project_dirs(base)
            save_rgb(src, base / "input" / "building.png")
            try:
                classification, api_log = classify_scenario_from_facade(base)
                entry = {
                    "filename": item["filename"],
                    "ok": True,
                    "scenario_id": classification.get("scenario_id"),
                    "confidence": classification.get("confidence"),
                    "building_type": classification.get("building_type"),
                    "reason": classification.get("reason"),
                    "fallback": bool(classification.get("fallback") or api_log.get("fallback")),
                    "api_error": api_log.get("error"),
                }
            except Exception as exc:
                entry = {"filename": item["filename"], "ok": False, "error": str(exc)}
            results.append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
