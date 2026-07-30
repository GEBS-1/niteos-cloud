# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cloud_app as ca

OUT_DIR = ROOT / "templates_catalog" / "export_for_edit"
ZIP_PATH = ROOT / "templates_catalog" / "niteos_templates_prompts.zip"

IES_MAP = {
    "magistral": ("IES_LINEAR", ca.IES_LINEAR),
    "xray": ("IES_XRAY", ca.IES_XRAY),
    "ntpark": ("IES_NT_PARK", ca.IES_NT_PARK),
}


def copy_ies(const_name: str, dest_dir: Path) -> str:
    src = ca.resolve_ies_source(getattr(ca, const_name))
    if not src or not src.exists():
        return ""
    target = dest_dir / src.name
    shutil.copy2(src, target)
    return src.name


def write_scenario_folder(scenario: dict) -> None:
    sid = scenario["id"]
    folder = OUT_DIR / "scenarios" / sid
    folder.mkdir(parents=True, exist_ok=True)

    pid = ca.product_id_for_scenario(scenario)
    product = ca.client_product_by_id(pid)
    const_name, const_val = IES_MAP[pid]

    ref = ca.scenario_reference_path(sid)
    ref_file = ""
    if ref and ref.exists():
        ref_file = f"reference{ref.suffix.lower()}"
        shutil.copy2(ref, folder / ref_file)

    rules_src = ca.SCENARIO_PROMPTS_DIR / f"{sid}.txt"
    if rules_src.exists():
        shutil.copy2(rules_src, folder / "prompt_rules.txt")

    prompt_full = ca.build_dealer_scenario_prompt(scenario, product)
    (folder / "prompt_full.txt").write_text(prompt_full, encoding="utf-8")

    ies_dir = folder / "ies"
    ies_dir.mkdir(exist_ok=True)
    ies_file = copy_ies(const_name, ies_dir)

    meta = {
        "id": sid,
        "name": scenario["name"],
        "description": scenario.get("description", ""),
        "category": scenario.get("category", ""),
        "product_id": pid,
        "product_name": product["name"],
        "ies_constant": const_name,
        "ies_filename": const_val,
        "ies_file_copied": ies_file,
        "reference_file": ref_file,
        "prompt_rules_file": "prompt_rules.txt",
        "prompt_full_file": "prompt_full.txt",
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_legacy_folder(lid: str, label: str, ref_name: str) -> None:
    folder = OUT_DIR / "legacy" / lid
    folder.mkdir(parents=True, exist_ok=True)

    binding = ca.DEALER_LEGACY_TEMPLATE_BINDINGS[lid]
    product = ca.client_product_by_id(binding["product_id"])
    const_name, const_val = IES_MAP[binding["product_id"]]

    ref_src = ROOT / "examples" / "style_references" / ref_name
    ref_file = ""
    if ref_src.exists():
        ref_file = f"reference{ref_src.suffix.lower()}"
        shutil.copy2(ref_src, folder / ref_file)

    prompt_full = ca.build_dealer_legacy_template_prompt(label, product)
    (folder / "prompt_full.txt").write_text(prompt_full, encoding="utf-8")
    (folder / "prompt_rules.txt").write_text(
        "# Legacy: add detailed lighting rules here.\n"
        "# Current backend uses prompt_full.txt only.\n",
        encoding="utf-8",
    )

    ies_dir = folder / "ies"
    ies_dir.mkdir(exist_ok=True)
    ies_file = copy_ies(const_name, ies_dir)

    meta = {
        "id": lid,
        "name": label,
        "product_id": binding["product_id"],
        "product_name": product["name"],
        "ies_constant": const_name,
        "ies_filename": const_val,
        "ies_file_copied": ies_file,
        "reference_file": ref_file,
        "prompt_rules_file": "prompt_rules.txt",
        "prompt_full_file": "prompt_full.txt",
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme() -> None:
    text = (
        "NITEOS templates edit package\n"
        "=============================\n\n"
        "scenarios/{id}/\n"
        "  reference.png\n"
        "  prompt_rules.txt   <- edit first\n"
        "  prompt_full.txt    <- current full prompt sent to generation\n"
        "  ies/*.ies\n"
        "  meta.json\n\n"
        "legacy/{legacy_N}/\n"
        "  reference.jpg|png\n"
        "  prompt_rules.txt\n"
        "  prompt_full.txt\n"
        "  ies/*.ies\n"
        "  meta.json\n\n"
        "shared/\n"
        "  style_ai_block.txt\n"
        "  all_prompts.md\n\n"
        "After edit, copy prompt_rules.txt back to:\n"
        "  exports/mvp-fixtures/scenarios/prompts/{id}.txt\n"
    )
    (OUT_DIR / "README.txt").write_text(text, encoding="utf-8")


def write_shared() -> None:
    shared = OUT_DIR / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "style_ai_block.txt").write_text(ca.CLIENT_STYLE_AI_BLOCK, encoding="utf-8")
    gen = ROOT / "templates_catalog" / "generate_prompts_file.py"
    prompts_md = ROOT / "templates_catalog" / "PROMPTS_FULL_RU.md"
    if gen.exists():
        subprocess.run([sys.executable, str(gen)], check=False)
    if prompts_md.exists():
        shutil.copy2(prompts_md, shared / "all_prompts.md")


def build_zip() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    for scenario in ca.CLIENT_SCENARIOS:
        write_scenario_folder(scenario)

    for lid, label, ref in [
        ("legacy_1", "\u0428\u0430\u0431\u043b\u043e\u043d 1", "1.jpg"),
        ("legacy_2", "\u0428\u0430\u0431\u043b\u043e\u043d 2", "2.png"),
        ("legacy_3", "\u0428\u0430\u0431\u043b\u043e\u043d 3", "3.jpg"),
        ("legacy_4", "\u0428\u0430\u0431\u043b\u043e\u043d 4", "4.jpg"),
    ]:
        write_legacy_folder(lid, label, ref)

    write_shared()
    write_readme()

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT_DIR.rglob("*")):
            if path.is_file():
                arcname = Path("templates_catalog") / "export_for_edit" / path.relative_to(OUT_DIR)
                zf.write(path, arcname.as_posix())

    print(str(ZIP_PATH))
    print("files:", sum(1 for _ in OUT_DIR.rglob("*") if _.is_file()))
    print("zip_bytes:", ZIP_PATH.stat().st_size)


if __name__ == "__main__":
    build_zip()
