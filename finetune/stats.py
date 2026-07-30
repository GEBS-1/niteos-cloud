# -*- coding: utf-8 -*-
"""Dataset stats helpers for admin/CLI."""
from __future__ import annotations

from pathlib import Path

from finetune.export_dataset import DEFAULT_OUT, dataset_stats, list_fewshot_targets


def get_finetune_dataset_stats(out_dir: Path | None = None) -> dict:
    stats = dataset_stats(out_dir)
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    stats["out_dir"] = str(out)
    stats["exists"] = out.exists()
    stats["fewshot_ready"] = len(list_fewshot_targets(2, out)) > 0
    return stats
