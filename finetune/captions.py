# -*- coding: utf-8 -*-
"""Build short training captions from scenario prompts / history prompts."""
from __future__ import annotations

import re
from pathlib import Path

from finetune import TRIGGER_TOKEN

_IDENTITY_TAIL = (
    "keep building geometry 1:1, no new pilasters or columns, "
    "preserve signs and plaques, architectural facade lighting only"
)

# Markers that start boilerplate blocks we strip from long prompts (RU/EN).
_NOISE_MARKERS = (
    "STROGOE",  # fallback ascii
    "\u0421\u0422\u0420\u041e\u0413\u041e\u0415 \u0421\u041e\u0425\u0420\u0410\u041d\u0415\u041d\u0418\u0415",
    "\u041e\u0431\u0449\u0438\u0435 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f \u043a \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0443",
    "LEARNING MEMORY",
    "AGENT LIGHTING PLACEMENT",
    "IMAGE ORDER:",
    "AUTO FACADE MODE",
    "\u0412\u0435\u0440\u0442\u0438\u043a\u0430\u043b\u044c\u043d\u044b\u0435 \u043f\u0440\u043e\u0436\u0435\u043a\u0442\u043e\u0440\u044b",
)


def _first_task_block(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    for marker in _NOISE_MARKERS:
        idx = raw.find(marker)
        if idx > 80:
            raw = raw[:idx].strip()
    m = re.search(
        r"(?:\u0417\u0430\u0434\u0430\u0447\u0430|Task):\s*(.+?)(?:\n\n|\n\u041d\u0435 |\n\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c |\n\u0421\u0446\u0435\u043d\u0430 |\Z)",
        raw,
        re.S,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    chunk = " ".join(lines[:6])
    return re.sub(r"\s+", " ", chunk)[:400].strip()


def compress_prompt_for_caption(
    prompt: str,
    *,
    scenario_id: str = "",
    scenario_name: str = "",
) -> str:
    task = _first_task_block(prompt)
    parts = [TRIGGER_TOKEN, "night architectural facade lighting visualization"]
    if scenario_name:
        parts.append(f"scenario {scenario_name}")
    elif scenario_id:
        parts.append(f"scenario {scenario_id}")
    if task:
        parts.append(task[:320])
    parts.append(_IDENTITY_TAIL)
    return ", ".join(p for p in parts if p)


def caption_from_prompt_file(path: Path, **kwargs) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    return compress_prompt_for_caption(text, **kwargs)


def write_caption(path: Path, caption: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(caption.strip() + "\n", encoding="utf-8")
