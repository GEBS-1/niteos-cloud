# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = [
    "linear_mix_full",
    "xray_columns",
    "linear_cornice",
    "xray_wash",
    "linear_mix_cv",
    "linear_mix_ch",
    "linear_mix_hv",
]


def main() -> None:
    prompts_dir = ROOT / "exports" / "mvp-fixtures" / "scenarios" / "prompts"
    bodies: dict[str, str] = {}
    for sid in IDS:
        text = (prompts_dir / f"{sid}.txt").read_text(encoding="utf-8")
        lines = text.splitlines()
        bodies[sid] = "\n".join(lines[3:]).strip() if len(lines) > 3 else text.strip()

    target = ROOT / "scenario_router_prompts.py"
    text = target.read_text(encoding="utf-8")
    start = text.index("SCENARIO_PROMPT_UPDATED_IDS")
    end = text.index("def scenario_prompt_updated")

    block = "SCENARIO_PROMPT_UPDATED_IDS = frozenset({\n"
    block += ",\n".join(f'    "{sid}"' for sid in IDS) + ",\n})\n\n"
    block += "SCENARIO_FULL_PROMPTS: dict[str, str] = {\n"
    for sid in IDS:
        block += f'    "{sid}": """\n{bodies[sid]}\n""",\n'
    block += "}\n\n\n"

    target.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print(f"embedded {len(bodies)} prompts into scenario_router_prompts.py")


if __name__ == "__main__":
    main()
