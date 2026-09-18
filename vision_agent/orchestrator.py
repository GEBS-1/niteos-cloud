# -*- coding: utf-8 -*-
"""Orchestrate Vision Agent Studio start + chat revision cycle."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from scenario_router_prompts import append_facade_identity_lock, build_scenario_image_prompt
from vision_agent.chat_agent import (
    STUDIO_MARKUP_CONTRACT,
    append_chat_message,
    intent_to_revision_prompt,
    parse_chat_intent,
    read_agent_state,
    read_chat_history,
    write_agent_state,
)
from vision_agent.facade_analyzer import analyze_facade_for_studio
from vision_agent.light_map import generate_agent_light_map
from vision_agent.placement_synthesizer import build_studio_render_prompt, synthesize_placement_plan
from vision_agent.reference_catalog import reference_path
from vision_agent.scheme_picker import pick_scheme_and_product
from vision_agent.style_matcher import match_references


class StudioDeps:
    """Callable dependencies injected from cloud_app to avoid circular imports."""

    def __init__(self, **kwargs: Any) -> None:
        self.analyze_facade_source: Callable = kwargs["analyze_facade_source"]
        self.prepare_image_for_vision: Callable = kwargs["prepare_image_for_vision"]
        self.call_routerai_vision_json: Callable = kwargs["call_routerai_vision_json"]
        self.call_routerai: Callable = kwargs["call_routerai"]
        self.apply_niteos_watermark: Callable = kwargs["apply_niteos_watermark"]
        self.save_render_history_entry: Callable = kwargs["save_render_history_entry"]
        self.write_project_meta: Callable = kwargs["write_project_meta"]
        self.read_project_meta: Callable = kwargs["read_project_meta"]
        self.append_pipeline_log: Callable = kwargs["append_pipeline_log"]
        self.edit_project_render: Callable = kwargs["edit_project_render"]
        self.client_scenario_by_id: Callable = kwargs["client_scenario_by_id"]
        self.client_product_by_id: Callable = kwargs["client_product_by_id"]
        self.apply_dealer_scenario: Callable = kwargs["apply_dealer_scenario"]
        self.resolve_routerai_model: Callable = kwargs["resolve_routerai_model"]
        self.classifier_model: str = kwargs.get("classifier_model") or ""
        self.save_annotation_upload: Callable | None = kwargs.get("save_annotation_upload")
        self.analyze_markup_colors: Callable | None = kwargs.get("analyze_markup_colors")


def _copy_primary_ref(base: Path, matched: list[dict]) -> str:
    if not matched:
        return ""
    src = reference_path(matched[0])
    if not src:
        return ""
    dst = base / "references" / "agent_ref_primary.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "references/agent_ref_primary.png"


def run_studio_start(base: Path, deps: StudioDeps, *, router_model: str = "") -> dict:
    source = base / "input" / "building.png"
    if not source.exists():
        raise RuntimeError("Upload a facade photo first")

    deps.write_project_meta(base, {"work_mode": "agent_studio", "mode": "agent_studio", "agent_studio": True, "status": "studio_analyzing"})
    deps.append_pipeline_log(base, "studio_start", {})

    analysis, analyze_log = analyze_facade_for_studio(
        base,
        analyze_facade_source=deps.analyze_facade_source,
        prepare_image_for_vision=deps.prepare_image_for_vision,
        call_routerai_vision_json=deps.call_routerai_vision_json,
        classifier_model=deps.classifier_model,
    )
    deps.append_pipeline_log(base, "studio_analyze", {"analysis": analysis, "api": analyze_log})

    matched, match_log = match_references(
        analysis,
        prepare_image_for_vision=deps.prepare_image_for_vision,
        call_routerai_vision_json=deps.call_routerai_vision_json,
        source_path=source,
        classifier_model=deps.classifier_model,
        limit=2,
    )
    deps.append_pipeline_log(base, "studio_match", {
        "matched": [m.get("id") for m in matched],
        "api": match_log,
    })

    scheme = pick_scheme_and_product(matched, analysis)
    placement = synthesize_placement_plan(analysis=analysis, scheme=scheme, matched_refs=matched)

    try:
        deps.apply_dealer_scenario(base, scheme["scenario_id"], scheme.get("product_id") or "")
    except Exception as exc:
        deps.append_pipeline_log(base, "studio_scenario_apply_error", {"error": str(exc)})

    try:
        scenario = deps.client_scenario_by_id(scheme["scenario_id"])
        scenario_prompt = build_scenario_image_prompt(
            scheme["scenario_id"],
            fallback_app=scenario.get("application_prompt", ""),
            facade_mode="auto",
        )
    except Exception:
        scenario_prompt = build_scenario_image_prompt(scheme["scenario_id"], facade_mode="auto")

    render_prompt = append_facade_identity_lock(
        build_studio_render_prompt(
            scenario_prompt=scenario_prompt,
            placement_plan=placement,
            scheme=scheme,
            analysis=analysis,
        )
    )
    (base / "prompt.txt").write_text(render_prompt, encoding="utf-8")

    ref_rel = _copy_primary_ref(base, matched)
    light_map_path = base / "output" / "agent_light_map.png"
    generate_agent_light_map(source, light_map_path, placement)

    images = [source]
    ref_file = base / "references" / "agent_ref_primary.png"
    if ref_file.exists():
        images.append(deps.prepare_image_for_vision(ref_file, max_side=1400))
    if light_map_path.exists():
        images.append(deps.prepare_image_for_vision(light_map_path, max_side=1400))

    model = deps.resolve_routerai_model(router_model)
    final_path = base / "output" / "final_imported_render.png"
    _, api_log = deps.call_routerai(
        render_prompt,
        images,
        final_path,
        project_base=base,
        model=model,
    )
    deps.apply_niteos_watermark(final_path)
    primary = matched[0] if matched else {}
    scenario_name = ""
    product_name = ""
    try:
        scenario_name = str(deps.client_scenario_by_id(scheme.get("scenario_id") or "").get("name") or "")
    except Exception:
        scenario_name = str(scheme.get("scenario_id") or "")
    try:
        meta_now = json.loads((base / "project.json").read_text(encoding="utf-8"))
    except Exception:
        meta_now = {}
    product_name = str(meta_now.get("dealer_product_name") or scheme.get("product_id") or "")
    # Write catalog meta BEFORE history so the entry gets scenario/product/work_mode.
    deps.write_project_meta(base, {
        "status": "rendered",
        "mode": "agent_studio",
        "work_mode": "agent_studio",
        "routerai_model": model,
        "render_scenario_id": scheme.get("scenario_id"),
        "render_scenario_name": scenario_name,
        "render_product_id": scheme.get("product_id"),
        "render_product_name": product_name,
        "matched_ref_id": primary.get("id") or "",
        "matched_ref_title": primary.get("title") or primary.get("id") or "",
        "matched_ref_cluster": primary.get("cluster") or scheme.get("cluster") or "",
        "reference_file": ref_rel or "references/agent_ref_primary.png",
        "agent_studio": True,
        "final": "output/final_imported_render.png",
        "last_placement_plan": placement,
        "feedback_required": True,
    })
    history = deps.save_render_history_entry(
        base,
        kind="studio_render",
        note=f"AI Studio · {scheme.get('cluster') or ''} · {scheme.get('scenario_id') or ''}".strip(" ·"),
        prompt=render_prompt,
    )
    deps.write_project_meta(base, {
        "last_history_entry": history,
        "feedback_required": True,
        "active_history_id": (history or {}).get("id"),
    })
    deps.append_pipeline_log(base, "studio_render", api_log)

    cluster = scheme.get("cluster") or ""
    cluster_ru = {
        "linear_cornice_bands": "линейные пояса / карнизы",
        "linear_contour_balcony": "контур балконов",
        "vertical_wash_stagger": "вертикальная заливка",
        "classical_heritage": "классический фасад",
        "mixed_commercial": "смешанная коммерческая",
        "entrance_accent": "акцент входа",
        "glass_glow": "свечение остекления",
    }.get(cluster, cluster or "по референсу")
    explanation = (
        f"Подобрал стиль освещения: {cluster_ru}. "
        "Референс и схема сохранены для дальнейших правок."
    )
    append_chat_message(
        base, "assistant", explanation, action="start", scheme=scheme,
        history_id=(history or {}).get("id"),
    )
    append_chat_message(
        base,
        "assistant",
        "Готово. Можно отметить светильники кистью/ластиком или написать правку в чат.",
        action="render_done",
        history_id=(history or {}).get("id"),
    )

    state = write_agent_state(base, {
        "status": "ready",
        "analysis": analysis,
        "matched_refs": [
            {"id": m.get("id"), "cluster": m.get("cluster"), "title": m.get("title")}
            for m in matched
        ],
        "scheme": scheme,
        "placement_plan": placement,
        "reference_file": ref_rel,
        "light_map_file": "output/agent_light_map.png" if light_map_path.exists() else "",
        "routerai_model": model,
        "last_prompt": render_prompt[:4000],
        "last_history_id": (history or {}).get("id"),
    })
    return {
        "ok": True,
        "state": state,
        "chat": read_chat_history(base),
        "explanation": explanation,
        "final": "output/final_imported_render.png",
        "history_entry": history,
    }


def run_studio_chat(
    base: Path,
    deps: StudioDeps,
    message: str,
    *,
    router_model: str = "",
    annotation_data_url: str | None = None,
    annotation_upload=None,
) -> dict:
    text = (message or "").strip()
    has_markup = bool(annotation_upload is not None or (annotation_data_url and str(annotation_data_url).startswith("data:")))
    if not text and not has_markup:
        raise RuntimeError("Empty message")
    if has_markup and not text:
        raise RuntimeError(
            "С разметкой нужно описать правку текстом: что убрать или изменить на отмеченных светильниках?"
        )

    markup_mode = ""
    markup_colors: dict = {}
    saved_annotation_path = None
    # Persist + classify paint early so chat/instruction match the stroke colors.
    if has_markup and deps.save_annotation_upload and deps.analyze_markup_colors:
        ann_path = base / "output" / "edit_annotation.png"
        saved = deps.save_annotation_upload(annotation_upload, annotation_data_url or "", ann_path)
        if saved is not None:
            saved_annotation_path = saved
            markup_colors = deps.analyze_markup_colors(saved) or {}
            markup_mode = str(markup_colors.get("mode") or "")
            # Upload stream is consumed; edit will use saved_annotation_path.
            annotation_upload = None
            annotation_data_url = None

    chat_text = text
    model_text = text

    append_chat_message(base, "user", chat_text, has_markup=has_markup, markup_mode=markup_mode or None)
    state = read_agent_state(base)
    intent = parse_chat_intent(model_text)
    if has_markup:
        # Paint edits must stay local — ignore global chat intents from wording like «убери».
        intent["remove_verticals"] = False
        intent["boost_cornice"] = False
        intent["boost_entrance"] = False
        intent["regenerate"] = False
        intent["action"] = "revise"
    revision = intent_to_revision_prompt(
        intent, state, has_markup=has_markup, markup_mode=markup_mode,
    )

    placement = dict(state.get("placement_plan") or {})
    scheme = dict(state.get("scheme") or {})
    if intent.get("remove_verticals"):
        placement["vertical_accents"] = False
    if intent.get("boost_cornice"):
        placement["continuous_lines"] = True
    if intent.get("temperature"):
        state["temperature"] = intent["temperature"]

    # Prefer explicit request model, else current server default — never pin to stale project meta.
    model = deps.resolve_routerai_model(router_model)
    history = None

    # Markup edits always go through edit path (not full regenerate), unless no final yet.
    force_regen = intent.get("regenerate") and not has_markup
    if force_regen or not (base / "output" / "final_imported_render.png").exists():
        analysis = state.get("analysis") or {}
        scenario_id = scheme.get("scenario_id") or "linear_cornice"
        try:
            scenario = deps.client_scenario_by_id(scenario_id)
            scenario_prompt = build_scenario_image_prompt(
                scenario_id,
                fallback_app=scenario.get("application_prompt", ""),
                facade_mode="auto",
            )
        except Exception:
            scenario_prompt = build_scenario_image_prompt(scenario_id, facade_mode="auto")
        render_prompt = append_facade_identity_lock(
            build_studio_render_prompt(
                scenario_prompt=scenario_prompt,
                placement_plan=placement,
                scheme=scheme,
                analysis=analysis,
                user_delta=revision,
            )
        )
        (base / "prompt.txt").write_text(render_prompt, encoding="utf-8")
        source = base / "input" / "building.png"
        images = [source]
        ref = base / "references" / "agent_ref_primary.png"
        if ref.exists():
            images.append(deps.prepare_image_for_vision(ref, max_side=1400))
        light_map = base / "output" / "agent_light_map.png"
        if light_map.exists():
            images.append(deps.prepare_image_for_vision(light_map, max_side=1400))
        final_path = base / "output" / "final_imported_render.png"
        _, api_log = deps.call_routerai(
            render_prompt, images, final_path, project_base=base, model=model
        )
        deps.apply_niteos_watermark(final_path)
        # Stamp AI Studio identity BEFORE history save (not after).
        deps.write_project_meta(base, {
            "mode": "agent_studio",
            "work_mode": "agent_studio",
            "agent_studio": True,
            "routerai_model": model,
            "last_placement_plan": placement,
        })
        history = deps.save_render_history_entry(
            base, kind="studio_regenerate", note=(chat_text or model_text)[:200], prompt=render_prompt
        )
        deps.write_project_meta(base, {
            "work_mode": "agent_studio",
            "agent_studio": True,
            "last_history_entry": history,
            "last_placement_plan": placement,
            "feedback_required": True,
            "active_history_id": (history or {}).get("id"),
        })
        deps.append_pipeline_log(base, "studio_chat_regenerate", api_log)
        reply = "Перегенерировал результат по вашему запросу."
    else:
        # With markup, color-based instruction is built inside edit_project_render.
        # Pass only optional user text as a clarification note.
        edit_instruction = text if has_markup else revision
        # Stamp AI Studio identity BEFORE edit history entry is written.
        deps.write_project_meta(base, {
            "mode": "agent_studio",
            "work_mode": "agent_studio",
            "agent_studio": True,
            "routerai_model": model,
            "last_placement_plan": placement,
        })
        edited = deps.edit_project_render(
            base,
            edit_instruction,
            annotation_data_url=annotation_data_url,
            annotation_upload=annotation_upload,
            router_model=model,
            markup_contract=STUDIO_MARKUP_CONTRACT if has_markup else "",
            history_kind="studio_edit",
            annotation_path=saved_annotation_path,
        )
        # edit_project_render already appended render_history; pick last entry.
        try:
            meta_now = json.loads((base / "project.json").read_text(encoding="utf-8"))
            hist_list = list(meta_now.get("render_history") or [])
            history = hist_list[-1] if hist_list else None
        except Exception:
            history = None
        deps.write_project_meta(base, {
            "mode": "agent_studio",
            "work_mode": "agent_studio",
            "agent_studio": True,
            "last_placement_plan": placement,
            "feedback_required": True,
            "active_history_id": (history or {}).get("id"),
        })
        deps.append_pipeline_log(base, "studio_chat_edit", {
            "instruction": revision,
            "path": str(edited),
            "has_markup": has_markup,
            "history_id": (history or {}).get("id"),
        })
        reply = (
            "Правка по разметке применена." if has_markup else "Правка применена."
        )

    append_chat_message(
        base, "assistant", reply,
        action=intent.get("action"), intent=intent, has_markup=has_markup,
        history_id=(history or {}).get("id"),
    )
    state = write_agent_state(base, {
        "placement_plan": placement,
        "scheme": scheme,
        "last_chat_intent": intent,
        "routerai_model": model,
        "status": "ready",
        "last_history_id": (history or {}).get("id"),
    })
    return {
        "ok": True,
        "reply": reply,
        "intent": intent,
        "state": state,
        "chat": read_chat_history(base),
        "final": "output/final_imported_render.png",
        "history_entry": history,
        "has_markup": has_markup,
    }


def restore_studio_history(base: Path, history_id) -> dict:
    """Copy a history PNG into final so subsequent edits start from that version."""
    meta_path = base / "project.json"
    if not meta_path.exists():
        raise RuntimeError("Project meta missing")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    history = list(meta.get("render_history") or [])
    target = None
    for item in history:
        if str(item.get("id")) == str(history_id):
            target = item
            break
    if not target:
        raise RuntimeError(f"History version not found: {history_id}")
    rel = str(target.get("file") or "")
    bare = rel.replace("\\", "/").split("/")[-1]
    if not bare:
        raise RuntimeError("History file missing in entry")
    src = base / "output" / "history" / bare
    if not src.exists():
        raise RuntimeError(f"History file not found on disk: {bare}")
    final_path = base / "output" / "final_imported_render.png"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, final_path)
    # Mark as active working version (no new history entry yet).
    write_meta = {
        "status": "history_restored",
        "final": "output/final_imported_render.png",
        "last_history_entry": target,
        "active_history_id": target.get("id"),
        "work_mode": "agent_studio",
        "agent_studio": True,
        # Don't force a new rating just for opening an old version.
        "feedback_required": False,
    }
    meta.update(write_meta)
    meta["updated_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_agent_state(base, {
        "active_history_id": target.get("id"),
        "status": "ready",
    })
    append_chat_message(
        base,
        "assistant",
        f"Активна версия №{target.get('id')}. Кисть/ластик и «Отправить» правят именно её.",
        action="restore_history",
        history_id=target.get("id"),
    )
    return {
        "ok": True,
        "restored_id": target.get("id"),
        "message": f"Версия №{target.get('id')} активна для правок",
    }


def set_studio_final_from_image(base: Path, deps: StudioDeps, image_path: Path, *, note: str = "") -> dict:
    """Install an uploaded/pasted image as the active final and history entry."""
    if not image_path.exists():
        raise RuntimeError("Image missing")
    final_path = base / "output" / "final_imported_render.png"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize via RGB save through PIL if available in deps path; use shutil for copy then watermark.
    shutil.copy2(image_path, final_path)
    try:
        deps.apply_niteos_watermark(final_path)
    except Exception:
        pass
    deps.write_project_meta(base, {
        "status": "final_set",
        "work_mode": "agent_studio",
        "agent_studio": True,
        "final": "output/final_imported_render.png",
        "feedback_required": False,
    })
    history = deps.save_render_history_entry(
        base,
        kind="studio_paste",
        note=(note or "Pasted/copied working render")[:200],
        prompt=note or "User pasted/copied image as working final",
    )
    deps.write_project_meta(base, {
        "last_history_entry": history,
        "active_history_id": (history or {}).get("id"),
    })
    append_chat_message(
        base,
        "assistant",
        "Рабочее фото обновлено из копии. Можно размечать светильники и отправлять правки.",
        action="set_final",
        history_id=(history or {}).get("id"),
    )
    write_agent_state(base, {
        "status": "ready",
        "active_history_id": (history or {}).get("id"),
    })
    return {"ok": True, "history_entry": history}


def get_studio_state(base: Path) -> dict:
    state = read_agent_state(base)
    meta = {}
    try:
        meta_path = base / "project.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    history = list(meta.get("render_history") or []) if isinstance(meta, dict) else []
    active_id = meta.get("active_history_id")
    if active_id is None:
        active_id = (meta.get("last_history_entry") or {}).get("id")
    history_urls = []
    for item in history[-12:]:
        fname = str((item or {}).get("file") or (item or {}).get("filename") or "")
        if not fname:
            continue
        bare = fname.replace("\\", "/").split("/")[-1]
        ann_rel = str((item or {}).get("annotation_file") or "").replace("\\", "/")
        ann_bare = ann_rel.split("/")[-1] if ann_rel else ""
        history_urls.append({
            "id": (item or {}).get("id") or bare,
            "url": f"/api/projects/{base.name}/file/history/{bare}",
            "note": (item or {}).get("note") or "",
            "kind": (item or {}).get("kind") or "",
            "created_at": (item or {}).get("created_at") or "",
            "prompt": ((item or {}).get("prompt") or "")[:300],
            "annotation_file": ann_rel,
            "annotation_url": (
                f"/api/projects/{base.name}/file/history/{ann_bare}"
                if ann_bare else ""
            ),
            "active": str((item or {}).get("id")) == str(active_id),
            "feedback_vote": (item or {}).get("feedback_vote") or "",
            "feedback_comment": (item or {}).get("feedback_comment") or "",
            "feedback_contact": (item or {}).get("feedback_contact") or "",
            "feedback_status": (item or {}).get("feedback_status") or "",
            "feedback_issue_type": (item or {}).get("feedback_issue_type") or "",
        })
    return {
        "ok": True,
        "state": state,
        "chat": read_chat_history(base),
        "has_source": (base / "input" / "building.png").exists(),
        "has_final": (base / "output" / "final_imported_render.png").exists(),
        "history": history_urls,
        "history_count": len(history),
        "active_history_id": active_id,
        # Derive from newest history vote — do not trust a one-shot meta flag
        # (restore / old skips could clear it while the latest result is still unrated).
        "feedback_required": (
            bool(history)
            and str(
                ((history[-1] if isinstance(history[-1], dict) else {}) or {}).get("feedback_vote") or ""
            ).strip().lower()
            not in {"like", "dislike"}
        ),
        "last_history_entry": (
            (history[-1] if history and isinstance(history[-1], dict) else None)
            or meta.get("last_history_entry")
            or {}
        ),
        "last_feedback_vote": meta.get("last_feedback_vote") or "",
        "routerai_model": (meta.get("routerai_model") or state.get("routerai_model") or ""),
        "reference_url": (
            f"/api/projects/{base.name}/file/references/agent_ref_primary.png"
            if (base / "references" / "agent_ref_primary.png").exists() else ""
        ),
        "light_map_url": (
            f"/api/projects/{base.name}/file/output/agent_light_map.png"
            if (base / "output" / "agent_light_map.png").exists() else ""
        ),
        "final_url": (
            f"/api/projects/{base.name}/file/output/final_imported_render.png"
            if (base / "output" / "final_imported_render.png").exists() else ""
        ),
        "source_url": (
            f"/api/projects/{base.name}/file/input/building.png"
            if (base / "input" / "building.png").exists() else ""
        ),
    }


def make_studio_deps_from_cloud(mod) -> StudioDeps:
    """Build StudioDeps from cloud_app module/globals."""
    return StudioDeps(
        analyze_facade_source=mod.analyze_facade_source,
        prepare_image_for_vision=mod.prepare_image_for_vision,
        call_routerai_vision_json=mod.call_routerai_vision_json,
        call_routerai=mod.call_routerai,
        apply_niteos_watermark=mod.apply_niteos_watermark,
        save_render_history_entry=mod.save_render_history_entry,
        write_project_meta=mod.write_project_meta,
        read_project_meta=mod.read_project_meta,
        append_pipeline_log=mod.append_pipeline_log,
        edit_project_render=mod.edit_project_render,
        client_scenario_by_id=mod.client_scenario_by_id,
        client_product_by_id=mod.client_product_by_id,
        apply_dealer_scenario=mod.apply_dealer_scenario,
        resolve_routerai_model=mod.resolve_routerai_model,
        classifier_model=getattr(mod, "AUTO_SCENARIO_CLASSIFIER_MODEL", "") or "",
        save_annotation_upload=mod.save_annotation_upload,
        analyze_markup_colors=mod.analyze_markup_colors,
    )
