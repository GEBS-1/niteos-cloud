# -*- coding: utf-8 -*-
"""Sync all catalog prompt .txt files from SCENARIO_FULL_PROMPTS + global rules."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scenario_router_prompts import SCENARIO_FULL_PROMPTS, attach_global_prompt_rules

OUT = ROOT / "exports" / "mvp-fixtures" / "scenarios" / "prompts"


def main() -> None:
    import cloud_app

    titles = {item["id"]: item["name"] for item in cloud_app.ALL_CLIENT_SCENARIOS}
    for sid, body in SCENARIO_FULL_PROMPTS.items():
        text = attach_global_prompt_rules(body)
        title = titles.get(sid, sid)
        content = (
            f"????????: {title}\n\n"
            f"??????? ????????????? ???????????:\n{text}\n"
        )
        (OUT / f"{sid}.txt").write_text(content, encoding="utf-8")
        print("ok", sid, "chars", len(text))


if __name__ == "__main__":
    main()
