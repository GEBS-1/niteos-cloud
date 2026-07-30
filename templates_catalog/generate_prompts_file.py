# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cloud_app as ca

IES_MAP = {
    "magistral": ("IES_LINEAR", ca.IES_LINEAR),
    "xray": ("IES_XRAY", ca.IES_XRAY),
    "ntpark": ("IES_NT_PARK", ca.IES_NT_PARK),
}


def ies_disk_path(const_name: str) -> str:
    src = ca.resolve_ies_source(getattr(ca, const_name))
    return src.relative_to(ROOT).as_posix() if src else "?"


def main() -> None:
    lines: list[str] = [
        "# NITEOS prompts (full text for all scenarios and legacy templates)\n",
        "\n",
        "Generated from cloud_app.py build_dealer_*_prompt functions.\n",
        "\n---\n",
        "\n## Scenarios (15)\n",
    ]

    for i, sc in enumerate(ca.CLIENT_SCENARIOS, 1):
        pid = ca.product_id_for_scenario(sc)
        product = ca.client_product_by_id(pid)
        const_name, const_val = IES_MAP[pid]
        ref = ca.scenario_reference_path(sc["id"])
        ref_path = ref.relative_to(ROOT).as_posix() if ref else "?"
        prompt = ca.build_dealer_scenario_prompt(sc, product)
        lines.append(f"\n### {i}. {sc['id']} - {sc['name']}\n\n")
        lines.append(f"- reference: `{ref_path}`\n")
        lines.append(f"- product: {product['name']} ({pid})\n")
        lines.append(f"- IES: `{const_val}`\n")
        lines.append(f"- IES file: `{ies_disk_path(const_name)}`\n\n")
        lines.append("```text\n")
        lines.append(prompt + "\n")
        lines.append("```\n\n---\n")

    lines.append("\n## Legacy templates (4)\n")
    legacy_items = [
        ("legacy_1", "1.jpg"),
        ("legacy_2", "2.png"),
        ("legacy_3", "3.jpg"),
        ("legacy_4", "4.jpg"),
    ]
    for i, (lid, fname) in enumerate(legacy_items, 1):
        binding = ca.DEALER_LEGACY_TEMPLATE_BINDINGS[lid]
        product = ca.client_product_by_id(binding["product_id"])
        const_name, const_val = IES_MAP[binding["product_id"]]
        lname = f"Template {i}"
        prompt = ca.build_dealer_legacy_template_prompt(lname, product)
        lref = f"examples/style_references/{fname}"
        lines.append(f"\n### {i}. {lid} - {lname}\n\n")
        lines.append(f"- reference: `{lref}`\n")
        lines.append(f"- product: {product['name']} ({binding['product_id']})\n")
        lines.append(f"- IES: `{const_val}`\n")
        lines.append(f"- IES file: `{ies_disk_path(const_name)}`\n\n")
        lines.append("```text\n")
        lines.append(prompt + "\n")
        lines.append("```\n\n---\n")

    out = ROOT / "templates_catalog" / "PROMPTS_FULL_RU.md"
    out.write_text("".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
