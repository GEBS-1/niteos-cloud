# -*- coding: utf-8 -*-
"""Sync architectural scenario prompt .txt files from SCENARIO_FULL_PROMPTS."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from architectural_catalog_ids import CATALOG_SCENARIO_ORDER
from scenario_router_prompts import SCENARIO_FULL_PROMPTS

OUT = ROOT / "exports" / "mvp-fixtures" / "scenarios" / "prompts"


def _scenario_titles() -> dict[str, str]:
    import cloud_app

    return {item["id"]: item["name"] for item in cloud_app.CLIENT_SCENARIOS}


def main() -> None:
    titles = _scenario_titles()
    for sid in CATALOG_SCENARIO_ORDER:
        body = SCENARIO_FULL_PROMPTS.get(sid, "").strip()
        if not body:
            raise SystemExit(f"missing prompt for {sid}")
        title = titles.get(sid, sid)
        content = (
            f"\u0421\u0426\u0415\u041d\u0410\u0420\u0418\u0419: {title}\n\n"
            f"\u041f\u0420\u0410\u0412\u0418\u041b\u0410 \u0418\u0421\u041f\u041e\u041b\u042c\u0417\u041e\u0412\u0410\u041d\u0418\u042f "
            f"\u0421\u0412\u0415\u0422\u0418\u041b\u042c\u041d\u0418\u041a\u0410:\n{body}\n"
        )
        (OUT / f"{sid}.txt").write_text(content, encoding="utf-8")
        print("ok", sid)


if __name__ == "__main__":
    main()
