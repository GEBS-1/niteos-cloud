# -*- coding: utf-8 -*-
"""Export fine-tune dataset from projects history, fixtures, viz, web refs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image

from finetune import DATASET_VERSION, TRIGGER_TOKEN
from finetune.captions import compress_prompt_for_caption, write_caption
from finetune.watermark import strip_niteos_watermark

# Allow large facade photos during export (still resized via _copy_rgb).
Image.MAX_IMAGE_PIXELS = 200_000_000

ROOT = Path(__file__).resolve().parent.parent
FINETUNE_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = FINETUNE_DIR / "data" / DATASET_VERSION
CLOUD_DIR = ROOT / "cloud_data"
WEB_MANIFEST = FINETUNE_DIR / "web_refs_manifest.json"
WEB_CACHE = FINETUNE_DIR / "data" / "web_cache"


def _safe_id(*parts: str) -> str:
    raw = "_".join(str(p or "").strip() for p in parts if str(p or "").strip())
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10]
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)[:48].strip("_")
    return f"{slug}_{digest}" if slug else digest


def _copy_rgb(src: Path, dst: Path, max_side: int = 2048) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_side:
                scale = max_side / float(max(w, h))
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            img.save(dst, format="PNG", optimize=True)
    except Exception:
        shutil.copy2(src, dst)


def _load_feedback_index(cloud_dir: Path) -> dict[tuple[str, str], str]:
    """Map (project_id, history_id) -> vote."""
    out: dict[tuple[str, str], str] = {}
    feedback_dir = cloud_dir / "feedback"
    if not feedback_dir.is_dir():
        return out
    for path in feedback_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        pid = str(data.get("project_id") or "")
        hid = str(data.get("render_history_id") or data.get("history_id") or "")
        vote = str(data.get("vote") or data.get("feedback_vote") or "").strip().lower()
        if pid and vote:
            out[(pid, hid)] = vote
            out[(pid, "")] = vote  # latest fallback
    return out


def _split_for(key: str) -> str:
    # Stable ~15% val
    return "val" if int(hashlib.md5(key.encode()).hexdigest()[:4], 16) % 100 < 15 else "train"


def _add_pair(
    *,
    out_dir: Path,
    sample_id: str,
    source: Path | None,
    target: Path,
    caption: str,
    meta: dict,
    strip_wm: bool,
) -> dict | None:
    if not target.exists():
        return None
    vote = (meta.get("vote") or "").lower()
    if vote == "dislike":
        return None

    pair_dir = out_dir / "pairs" / sample_id
    pair_dir.mkdir(parents=True, exist_ok=True)
    target_out = pair_dir / "target.png"
    if strip_wm:
        strip_niteos_watermark(target, target_out)
    else:
        _copy_rgb(target, target_out)

    source_out = ""
    if source and source.exists():
        sp = pair_dir / "source.png"
        _copy_rgb(source, sp)
        source_out = "source.png"

    cap_path = pair_dir / "caption.txt"
    write_caption(cap_path, caption)

    split = meta.get("split") or _split_for(sample_id)
    meta_out = {
        **meta,
        "id": sample_id,
        "split": split,
        "source_file": source_out,
        "target_file": "target.png",
        "caption_file": "caption.txt",
        "trigger": TRIGGER_TOKEN,
    }
    (pair_dir / "meta.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Kohya-style: images in train/img with matching .txt captions beside them
    # (or captions dir � we put .txt next to image in img/)
    if split == "train":
        img_name = f"{sample_id}.png"
        img_dst = out_dir / "train" / "img" / img_name
        _copy_rgb(target_out, img_dst)
        write_caption(out_dir / "train" / "img" / f"{sample_id}.txt", caption)
        # also captions folder mirror
        write_caption(out_dir / "train" / "captions" / f"{sample_id}.txt", caption)

    return meta_out


def collect_from_projects(cloud_dir: Path, out_dir: Path, strip_wm: bool) -> list[dict]:
    feedback = _load_feedback_index(cloud_dir)
    projects = cloud_dir / "projects"
    rows: list[dict] = []
    if not projects.is_dir():
        return rows

    for base in sorted(projects.iterdir()):
        if not base.is_dir():
            continue
        source = base / "input" / "building.png"
        meta_path = base / "project.json"
        project_meta: dict = {}
        if meta_path.exists():
            try:
                project_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                project_meta = {}
        history = list(project_meta.get("render_history") or [])

        if history:
            for entry in history:
                if not isinstance(entry, dict):
                    continue
                rel = str(entry.get("file") or "")
                target = (base / "output" / rel) if rel else None
                if target is None or not target.exists():
                    continue
                hid = str(entry.get("id") or "")
                vote = (
                    str(entry.get("feedback_vote") or "").lower()
                    or feedback.get((base.name, hid), "")
                    or feedback.get((base.name, ""), "")
                )
                prompt = str(entry.get("prompt") or "")
                prompt_file = entry.get("prompt_file") or ""
                if not prompt and prompt_file:
                    pf = base / "output" / str(prompt_file)
                    if pf.exists():
                        prompt = pf.read_text(encoding="utf-8", errors="ignore")
                sid = entry.get("scenario_id") or project_meta.get("dealer_scenario_id") or ""
                sname = entry.get("scenario_name") or project_meta.get("dealer_scenario_name") or ""
                caption = compress_prompt_for_caption(prompt, scenario_id=str(sid), scenario_name=str(sname))
                sample_id = _safe_id("hist", base.name, hid)
                row = _add_pair(
                    out_dir=out_dir,
                    sample_id=sample_id,
                    source=source if source.exists() else None,
                    target=target,
                    caption=caption,
                    meta={
                        "source_kind": "project_history",
                        "project_id": base.name,
                        "history_id": hid,
                        "vote": vote,
                        "quality": "good" if vote == "like" else ("bad" if vote == "dislike" else "unrated"),
                        "scenario_id": sid,
                        "scenario_name": sname,
                    },
                    strip_wm=strip_wm,
                )
                if row:
                    rows.append(row)
        else:
            # Fallback: latest final only
            final = base / "output" / "final_imported_render.png"
            if not final.exists():
                continue
            prompt_path = base / "prompt.txt"
            prompt = prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else ""
            vote = feedback.get((base.name, ""), "")
            sid = project_meta.get("dealer_scenario_id") or ""
            sname = project_meta.get("dealer_scenario_name") or ""
            caption = compress_prompt_for_caption(prompt, scenario_id=str(sid), scenario_name=str(sname))
            sample_id = _safe_id("final", base.name)
            row = _add_pair(
                out_dir=out_dir,
                sample_id=sample_id,
                source=source if source.exists() else None,
                target=final,
                caption=caption,
                meta={
                    "source_kind": "project_final",
                    "project_id": base.name,
                    "history_id": "",
                    "vote": vote,
                    "quality": "good" if vote == "like" else ("bad" if vote == "dislike" else "unrated"),
                    "scenario_id": sid,
                    "scenario_name": sname,
                },
                strip_wm=strip_wm,
            )
            if row:
                rows.append(row)
    return rows


def collect_from_generations(cloud_dir: Path, out_dir: Path, strip_wm: bool) -> list[dict]:
    gen_dir = cloud_dir / "generations"
    rows: list[dict] = []
    if not gen_dir.is_dir():
        return rows
    for path in sorted(gen_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        pid = str(data.get("project_id") or "")
        base = cloud_dir / "projects" / pid
        hist_file = str(data.get("history_file") or "")
        target = (base / "output" / hist_file) if hist_file else None
        if target is None or not target.exists():
            final_rel = str(data.get("final_file") or "")
            target = (base / final_rel) if final_rel else None
        if target is None or not target.exists():
            continue
        source_rel = str(data.get("source_file") or "input/building.png")
        source = base / source_rel
        vote = str(data.get("feedback_vote") or "").lower()
        prompt = str(data.get("prompt") or "")
        sid = data.get("scenario_id") or ""
        sname = data.get("scenario_name") or ""
        caption = compress_prompt_for_caption(prompt, scenario_id=str(sid), scenario_name=str(sname))
        sample_id = _safe_id("gen", path.stem)
        row = _add_pair(
            out_dir=out_dir,
            sample_id=sample_id,
            source=source if source.exists() else None,
            target=target,
            caption=caption,
            meta={
                "source_kind": "generation_archive",
                "project_id": pid,
                "history_id": str(data.get("history_id") or ""),
                "vote": vote,
                "quality": "good" if vote == "like" else ("bad" if vote == "dislike" else "unrated"),
                "scenario_id": sid,
                "scenario_name": sname,
                "archive": path.name,
            },
            strip_wm=strip_wm,
        )
        if row:
            rows.append(row)
    return rows


def collect_from_fixtures(out_dir: Path, strip_wm: bool) -> list[dict]:
    rows: list[dict] = []
    scenarios_dir = ROOT / "exports" / "mvp-fixtures" / "scenarios"
    prompts_dir = scenarios_dir / "prompts"
    lib_scenarios = ROOT / "cloud_data" / "library" / "style_references" / "scenarios"

    pngs = list(scenarios_dir.glob("*.png")) if scenarios_dir.is_dir() else []
    if lib_scenarios.is_dir():
        pngs.extend(lib_scenarios.glob("*.png"))

    seen: set[str] = set()
    for png in sorted(pngs):
        sid = png.stem
        if sid in seen:
            continue
        seen.add(sid)
        prompt = ""
        for candidate in (
            prompts_dir / f"{sid}.txt",
            lib_scenarios / f"{sid}.txt",
        ):
            if candidate.exists():
                prompt = candidate.read_text(encoding="utf-8", errors="ignore")
                break
        if not prompt:
            try:
                from scenario_router_prompts import SCENARIO_FULL_PROMPTS

                prompt = SCENARIO_FULL_PROMPTS.get(sid, "")
            except Exception:
                prompt = f"Architectural facade lighting scenario {sid}."
        caption = compress_prompt_for_caption(prompt, scenario_id=sid, scenario_name=sid)
        sample_id = _safe_id("fixture", sid)
        row = _add_pair(
            out_dir=out_dir,
            sample_id=sample_id,
            source=None,
            target=png,
            caption=caption,
            meta={
                "source_kind": "mvp_fixture",
                "project_id": "",
                "history_id": "",
                "vote": "like",
                "quality": "good",
                "scenario_id": sid,
                "scenario_name": sid,
            },
            strip_wm=strip_wm,
        )
        if row:
            rows.append(row)
    return rows


def collect_from_viz(out_dir: Path, strip_wm: bool) -> list[dict]:
    rows: list[dict] = []
    viz_dir = ROOT / "assets" / "viz_examples" / "examples"
    if not viz_dir.is_dir():
        return rows
    for img in sorted(viz_dir.iterdir()):
        if img.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        caption = compress_prompt_for_caption(
            "Professional night architectural facade lighting reference, "
            "realistic beams and linear accents, presentation quality.",
            scenario_id="viz_example",
            scenario_name="viz_example",
        )
        sample_id = _safe_id("viz", img.stem)
        row = _add_pair(
            out_dir=out_dir,
            sample_id=sample_id,
            source=None,
            target=img,
            caption=caption,
            meta={
                "source_kind": "viz_example",
                "project_id": "",
                "history_id": "",
                "vote": "like",
                "quality": "good",
                "scenario_id": "viz_example",
                "scenario_name": "viz_example",
                "orig_name": img.name,
            },
            strip_wm=strip_wm,
        )
        if row:
            rows.append(row)
    return rows


def collect_from_web_refs(out_dir: Path, strip_wm: bool, download: bool) -> list[dict]:
    rows: list[dict] = []
    if not WEB_MANIFEST.exists():
        return rows
    try:
        items = json.loads(WEB_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return rows
    if not isinstance(items, list):
        return rows
    WEB_CACHE.mkdir(parents=True, exist_ok=True)
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        local_name = str(item.get("id") or _safe_id("web", url)) + ".png"
        local = WEB_CACHE / local_name
        if not local.exists():
            if not download or not url:
                # allow pre-seeded local_path
                lp = item.get("local_path")
                if lp:
                    src = ROOT / str(lp)
                    if src.exists():
                        _copy_rgb(src, local)
                if not local.exists():
                    continue
            else:
                try:
                    urllib.request.urlretrieve(url, local)
                except Exception:
                    continue
        caption = compress_prompt_for_caption(
            str(item.get("caption") or "Night architectural facade lighting reference."),
            scenario_id=str(item.get("scenario_id") or "web_ref"),
            scenario_name=str(item.get("title") or "web_ref"),
        )
        sample_id = _safe_id("web", item.get("id") or local.stem)
        row = _add_pair(
            out_dir=out_dir,
            sample_id=sample_id,
            source=None,
            target=local,
            caption=caption,
            meta={
                "source_kind": "web_ref",
                "project_id": "",
                "history_id": "",
                "vote": "like",
                "quality": "good",
                "scenario_id": item.get("scenario_id") or "web_ref",
                "scenario_name": item.get("title") or "web_ref",
                "attribution": item.get("attribution") or "",
                "license": item.get("license") or "",
                "url": url,
            },
            strip_wm=strip_wm,
        )
        if row:
            rows.append(row)
    return rows


def extract_prod_tarball(tarball: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:*") as tf:
        tf.extractall(dest)
    # Prefer extracted cloud_data
    for candidate in (dest / "cloud_data", dest):
        if (candidate / "projects").is_dir():
            return candidate
    return dest


def export_dataset(
    *,
    cloud_dir: Path | None = None,
    out_dir: Path | None = None,
    include_fixtures: bool = True,
    include_viz: bool = True,
    include_web: bool = True,
    download_web: bool = False,
    strip_wm: bool = True,
    from_prod_tarball: Path | None = None,
) -> dict:
    cloud = Path(cloud_dir) if cloud_dir else CLOUD_DIR
    out = Path(out_dir) if out_dir else DEFAULT_OUT

    if from_prod_tarball:
        extract_root = FINETUNE_DIR / "data" / "_prod_extract"
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        cloud = extract_prod_tarball(Path(from_prod_tarball), extract_root)

    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    (out / "train" / "img").mkdir(parents=True, exist_ok=True)
    (out / "train" / "captions").mkdir(parents=True, exist_ok=True)
    (out / "pairs").mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    rows.extend(collect_from_projects(cloud, out, strip_wm))
    # generations may duplicate history � skip ids already present
    existing = {r["id"] for r in rows}
    for row in collect_from_generations(cloud, out, strip_wm):
        if row["id"] not in existing:
            rows.append(row)
            existing.add(row["id"])
    if include_fixtures:
        for row in collect_from_fixtures(out, strip_wm):
            if row["id"] not in existing:
                rows.append(row)
                existing.add(row["id"])
    if include_viz:
        for row in collect_from_viz(out, strip_wm):
            if row["id"] not in existing:
                rows.append(row)
                existing.add(row["id"])
    if include_web:
        for row in collect_from_web_refs(out, strip_wm, download=download_web):
            if row["id"] not in existing:
                rows.append(row)
                existing.add(row["id"])

    manifest_path = out / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = summarize_rows(rows)
    summary.update({
        "out_dir": str(out),
        "cloud_dir": str(cloud),
        "trigger": TRIGGER_TOKEN,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "train_images": len(list((out / "train" / "img").glob("*.png"))),
        "pairs": len(list((out / "pairs").iterdir())) if (out / "pairs").exists() else 0,
    })
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def summarize_rows(rows: list[dict]) -> dict:
    by_kind = Counter(r.get("source_kind") or "" for r in rows)
    by_vote = Counter((r.get("vote") or "none") or "none" for r in rows)
    by_split = Counter(r.get("split") or "" for r in rows)
    by_scenario = Counter(str(r.get("scenario_id") or "") for r in rows)
    return {
        "total": len(rows),
        "by_kind": dict(by_kind),
        "by_vote": dict(by_vote),
        "by_split": dict(by_split),
        "scenarios": len([k for k in by_scenario if k]),
        "scenario_ids": sorted(k for k in by_scenario if k)[:80],
        "good_pairs": sum(1 for r in rows if r.get("quality") == "good"),
    }


def dataset_stats(out_dir: Path | None = None) -> dict:
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    summary_path = out / "summary.json"
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    rows = []
    manifest = out / "manifest.jsonl"
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return summarize_rows(rows) if rows else {"total": 0, "exists": out.exists(), "out_dir": str(out)}


def list_fewshot_targets(limit: int = 2, out_dir: Path | None = None) -> list[Path]:
    """Prefer good/like pair targets for soft fine-tune mode."""
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    pairs = out / "pairs"
    if not pairs.is_dir():
        # fallback fixtures
        fixtures = ROOT / "exports" / "mvp-fixtures" / "scenarios"
        return sorted(fixtures.glob("*.png"))[:limit] if fixtures.is_dir() else []
    scored: list[tuple[int, Path]] = []
    for pair in pairs.iterdir():
        if not pair.is_dir():
            continue
        meta_path = pair / "meta.json"
        target = pair / "target.png"
        if not target.exists():
            continue
        score = 0
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
            if meta.get("vote") == "like" or meta.get("quality") == "good":
                score += 2
            if meta.get("source_kind") in {"project_history", "generation_archive"}:
                score += 1
            if meta.get("source_kind") == "mvp_fixture":
                score += 1
        scored.append((score, target))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [p for _, p in scored[: max(1, limit)]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export NITEOS Flux LoRA dataset")
    parser.add_argument("--cloud-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--from-prod-tarball", type=Path, default=None)
    parser.add_argument("--no-fixtures", action="store_true")
    parser.add_argument("--no-viz", action="store_true")
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--download-web", action="store_true")
    parser.add_argument("--keep-watermark", action="store_true")
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args(argv)

    if args.stats_only:
        print(json.dumps(dataset_stats(args.out_dir), ensure_ascii=False, indent=2))
        return 0

    summary = export_dataset(
        cloud_dir=args.cloud_dir,
        out_dir=args.out_dir,
        include_fixtures=not args.no_fixtures,
        include_viz=not args.no_viz,
        include_web=not args.no_web,
        download_web=args.download_web,
        strip_wm=not args.keep_watermark,
        from_prod_tarball=args.from_prod_tarball,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
