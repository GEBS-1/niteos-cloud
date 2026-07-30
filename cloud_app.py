from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal
import urllib.error
import urllib.request

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from dotenv import load_dotenv

from ai_packager_v29 import build_enhanced_task, build_ies_ai_prompt_block, load_ies_infos_from_dir
from architectural_catalog_ids import (
    CATALOG_PRODUCT_ID,
    CATALOG_SCENARIO_ORDER,
)
from scenario_router_prompts import (
    PROMPT_AUTO_FACADE_HARD_RULES,
    append_facade_identity_lock,
    build_router_image_prompt,
    build_scenario_image_prompt,
    router_task_for_scenario,
    scenario_prompt_updated,
)
from vision_agent.orchestrator import (
    get_studio_state,
    make_studio_deps_from_cloud,
    restore_studio_history,
    run_studio_chat,
    run_studio_start,
    set_studio_final_from_image,
)
from vision_agent.reference_catalog import EXAMPLES_DIR, THUMBS_DIR, get_reference_by_id, list_references_public, reference_path
from vision_agent.studio_html import AGENT_STUDIO_HTML


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
CLOUD_DIR = ROOT / "cloud_data"
PROJECTS_DIR = CLOUD_DIR / "projects"
LIBRARY_DIR = CLOUD_DIR / "library"
SOURCE_LIBRARY_DIR = LIBRARY_DIR / "source_photos"
IES_LIBRARY_DIR = LIBRARY_DIR / "ies"
STYLE_LIBRARY_DIR = LIBRARY_DIR / "style_references"
FIXTURES_LIBRARY_DIR = LIBRARY_DIR / "fixtures"
IES_CATALOG_DIR = ROOT / "assets" / "ies-catalog"
VIZ_EXAMPLES_DIR = ROOT / "assets" / "viz_examples" / "examples"
VIZ_THUMBS_DIR = ROOT / "assets" / "viz_examples" / "thumbs"
CLIENT_TEMPLATES_DIR = CLOUD_DIR / "client_templates"
LEARNING_DIR = CLOUD_DIR / "learning"
LEARNING_EVENTS_PATH = LEARNING_DIR / "events.jsonl"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

for path in (PROJECTS_DIR, SOURCE_LIBRARY_DIR, IES_LIBRARY_DIR, STYLE_LIBRARY_DIR, FIXTURES_LIBRARY_DIR, IES_CATALOG_DIR, CLIENT_TEMPLATES_DIR, LEARNING_DIR):
    path.mkdir(parents=True, exist_ok=True)

CONTACT_PHONE = os.getenv("CONTACT_PHONE", "+70123456789").strip()
MAX_GROUP_JOIN_URL = os.getenv(
    "MAX_GROUP_JOIN_URL",
    "https://max.ru/join/srh_oL9y5t9jt9ZCA_wkQ1dXP5DjO0WmMO7a8IbSi3k",
).strip()
CATALOG_ADMIN_PASSWORD = os.getenv("CATALOG_ADMIN_PASSWORD", "").strip()
# Лимит генераций по cookie — пока отключён (включить: RENDER_LIMIT_ENABLED = True)
RENDER_LIMIT_ENABLED = False
USAGE_DIR = CLOUD_DIR / "visitor_usage"
FEEDBACK_DIR = CLOUD_DIR / "feedback"
GENERATIONS_DIR = CLOUD_DIR / "generations"
IP_ACTIVITY_DIR = CLOUD_DIR / "ip_activity"
USAGE_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
GENERATIONS_DIR.mkdir(parents=True, exist_ok=True)
IP_ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
VISITOR_COOKIE = "niteos_vid"
DAILY_RENDER_LIMIT = max(1, int(os.getenv("DAILY_RENDER_LIMIT", "3")))
AUTO_REVIEW_CRITIC_MODEL = os.getenv("AUTO_REVIEW_CRITIC_MODEL", "").strip()
AUTO_REVIEW_ECONOMIC_CRITIC_MODEL = os.getenv("AUTO_REVIEW_ECONOMIC_CRITIC_MODEL", "openai/gpt-5.6-luna").strip()
AUTO_REVIEW_FULL_CRITIC_MODEL = os.getenv("AUTO_REVIEW_FULL_CRITIC_MODEL", "google/gemini-3.1-pro-preview").strip()
AUTO_REVIEW_MAX_REVISIONS = max(0, min(2, int(os.getenv("AUTO_REVIEW_MAX_REVISIONS", "2"))))
AUTO_REVIEW_MIN_CONFIDENCE = max(0.0, min(1.0, float(os.getenv("AUTO_REVIEW_MIN_CONFIDENCE", "0.65"))))
AUTO_SCENARIO_CLASSIFIER_MODEL = os.getenv(
    "AUTO_SCENARIO_CLASSIFIER_MODEL",
    AUTO_REVIEW_CRITIC_MODEL or AUTO_REVIEW_ECONOMIC_CRITIC_MODEL or "openai/gpt-5.6-luna",
).strip()
_usage_lock = threading.Lock()


def max_group_widget_html() -> str:
    """Плавающий виджет QR + ссылка на группу MAX (правый нижний угол — не перекрывает шапку)."""
    if not MAX_GROUP_JOIN_URL:
        return ""
    from urllib.parse import quote
    url = MAX_GROUP_JOIN_URL
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=104x104&data={quote(url, safe='')}"
    return f"""
<style>
.max-group-fab{{
  position:fixed;bottom:14px;right:14px;z-index:40;
  display:flex;align-items:center;gap:8px;
  padding:7px 11px 7px 7px;border-radius:12px;border:1px solid #3a4552;
  background:rgba(9,13,18,.94);backdrop-filter:blur(8px);
  color:#dce9f8;text-decoration:none;font-size:12px;font-weight:600;line-height:1.25;
  box-shadow:0 8px 28px rgba(0,0,0,.38);max-width:min(210px,calc(100vw - 24px));
}}
.max-group-fab:hover{{border-color:#5a8fd4;color:#fff}}
.max-group-fab img{{width:44px;height:44px;border-radius:8px;background:#fff;display:block;flex-shrink:0}}
@media(max-width:520px){{
  .max-group-fab span{{display:none}}
  .max-group-fab img{{width:40px;height:40px}}
  .max-group-fab{{bottom:10px;right:10px}}
}}
</style>
<a class="max-group-fab" href="{url}" target="_blank" rel="noopener noreferrer" title="Вступить в группу MAX">
  <img src="{qr_url}" width="44" height="44" alt="QR: группа MAX" loading="lazy">
  <span>Группа<br>в MAX</span>
</a>
"""


def inject_page_widgets(html: str) -> str:
    widget = max_group_widget_html()
    return html.replace("{{MAX_GROUP_WIDGET}}", widget)


IES_LINEAR = "МАГИСТРАЛЬ 205 170 ЛмВт [КОНСОЛЬ] Д.ies"
IES_XRAY = "NT-WAY 170 (Л) Г61 5000К, 4000К.ies"
IES_NT_PARK = "NT-STEP 100 A3 Д120 4000K.ies"

ROUTERAI_IMAGE_MODELS: list[dict[str, str]] = [
    {
        "id": "niteos/finetuned-lora",
        "label": "NITEOS LoRA · дообученная (архитектурный свет)",
        "eta": "~30–90 сек",
        "eta_sec": "60",
        "note": "Flux LoRA endpoint или soft few-shot, пока веса не подключены",
    },
    {
        "id": "google/gemini-3.1-flash-image-preview",
        "label": "Nano Banana 2 · Gemini 3.1 Flash Image (preview)",
        "eta": "~25–50 сек",
        "eta_sec": "40",
    },
    {
        "id": "google/gemini-3.1-flash-image",
        "label": "Nano Banana 2 · Gemini 3.1 Flash Image",
        "eta": "~25–50 сек",
        "eta_sec": "40",
    },
    {
        "id": "google/gemini-2.5-flash-image",
        "label": "Nano Banana · Gemini 2.5 Flash Image",
        "eta": "~20–40 сек",
        "eta_sec": "30",
    },
    {
        "id": "google/gemini-3-pro-image",
        "label": "Nano Banana Pro · Gemini 3 Pro Image",
        "eta": "~1–2 мин",
        "eta_sec": "90",
    },
    {
        "id": "openai/gpt-5-image",
        "label": "GPT-5 Image (OpenAI)",
        "eta": "~3–10 мин",
        "eta_sec": "360",
    },
]
ROUTERAI_MODEL_ALIASES: dict[str, str] = {
  # Раньше в селекторе ошибочно был gpt-5.5 (текстовая модель)
    "openai/gpt-5.5": "openai/gpt-5-image",
}
FINETUNED_MODEL_ID = "niteos/finetuned-lora"
SOFT_FINETUNE_BASE_MODEL = "google/gemini-3.1-flash-image-preview"


def infer_product_name_from_ies(ies_names: list[str]) -> str:
    blob = " ".join(ies_names).upper()
    if "МАГИСТРАЛЬ" in blob or "MAGISTRAL" in blob:
        return "MAGISTRAL v 3.0 AI 70"
    if "NT-STEP" in blob or "NT-PARK" in blob or "PARK" in blob:
        return "NT-park STEP"
    if "NT-WAY" in blob or "X-RAY" in blob or "XRAY" in blob:
        return "X-RAY ARCH"
    return ""
EXPORTS_FIXTURES_DIR = ROOT / "exports" / "mvp-fixtures"
SCENARIOS_DIR = EXPORTS_FIXTURES_DIR / "scenarios"
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)

CLIENT_STYLE_AI_BLOCK = (
    "Style ref — ОБРАЗЕЦ схемы подсветки: перенести ту же логику света (зоны, направление, "
    "плотность, характер) на здание клиента с исходного фото. Геометрию здания с образца "
    "НЕ копировать — только принцип подсветки. Осветить всё здание в кадре слева направо."
)

DEALER_STYLE_AI_BLOCK = (
    "Style ref — только качество: реализм, ночь, контраст, мягкий объемный свет. Архитектуру не копировать."
)


CLIENT_EXAMPLE_INSTRUCTION = (
    "Главная задача: добавить ночную подсветку на исходное фото (изображение 1). "
    "Здание на фото 1 — единственный источник архитектуры: сохранить 1:1 геометрию, "
    "этажность, окна, стекло, панели, цвет, деревянные рейки и все декоративные элементы.\n"
    "IES-файлы проекта — источник типа светильника и характера светового пятна (КСС, ширина луча, монтаж). "
    "Корпус — product front, фотометрия — IES. При конфликте light plan/style ref с IES — приоритет у IES.\n"
    "Style reference (изображение 3) — только схема света: какие зоны подсвечены, "
    "горизонтально или вертикально, плотность. НЕ копировать здание, фасад, окна и объекты с образца.\n"
    "Осветить всё здание на фото 1 слева направо по выбранному сценарию. "
    "Не добавлять типы светильников и зоны, которых нет в сценарии и загруженных IES."
)

SCENARIO_FORBIDDEN: dict[str, str] = {
    "linear_cornice": (
        "ЗАПРЕЩЕНО: горизонтальные линейные пояса между этажами; контурная/линейная подсветка по карнизу и кровле; "
        "заливающая подсветка всей плоскости; сплошные вертикальные LED-полосы (только прожекторные лучи «верх-вниз»); "
        "парковые столбы; подсветка на декоративных рейках; изменение материалов и геометрии фасада."
    ),
    "linear_horizontal": (
        "ЗАПРЕЩЕНО: вертикальные линии и лучи; прожекторы и точечные светильники; "
        "подсветка на декоративных рейках, ламелях и деревянных планках; линия по карнизу и кровле; "
        "изменение материалов, цвета панелей, окон, дерева и геометрии фасада."
    ),
    "linear_vertical": (
        "ЗАПРЕЩЕНО: горизонтали между этажами; линия по карнизу; прожекторы; споты; столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "linear_mix_ch": (
        "ЗАПРЕЩЕНО: чисто вертикальные линейные полосы без прожекторных акцентов; заливающая подсветка; "
        "парковые столбы; подсветка на декоративных рейках; изменение материалов и геометрии фасада."
    ),
    "linear_mix_cv": (
        "ЗАПРЕЩЕНО: горизонтали между этажами; заливающая подсветка всей плоскости; "
        "сплошные вертикальные LED-полосы (вертикаль — только прожекторные акценты); парковые столбы; "
        "подсветка на декоративных рейках; изменение материалов и геометрии фасада."
    ),
    "linear_mix_hv": (
        "ЗАПРЕЩЕНО: парковые столбы; подсветка на декоративных рейках вне сценария; "
        "изменение материалов и геометрии фасада."
    ),
    "linear_mix_full": (
        "ЗАПРЕЩЕНО: прожекторы; споты; столбы; подсветка на декоративных рейках вне сценария; "
        "изменение материалов и геометрии фасада."
    ),
    "linear_top_bottom": (
        "ЗАПРЕЩЕНО: горизонтали на средних этажах; вертикали; прожекторы; споты; столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "xray_wash": (
        "ЗАПРЕЩЕНО: LED-линейные полосы; вертикальные лучи; парковые столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "xray_columns": (
        "ЗАПРЕЩЕНО: сплошная заливка всего фасада; LED-полосы; столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "xray_openings": (
        "ЗАПРЕЩЕНО: сплошная заливка всего фасада; LED-полосы; столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "xray_graze": (
        "ЗАПРЕЩЕНО: равномерная заливка; LED-полосы; столбы; "
        "изменение материалов и геометрии фасада."
    ),
    "park_row": (
        "ЗАПРЕЩЕНО: светильники на фасаде; LED-линии на стене; прожекторы на здании; "
        "изменение материалов и геометрии фасада."
    ),
    "park_entrance": (
        "ЗАПРЕЩЕНО: светильники на фасаде; LED-линии на стене; прожекторы на здании; "
        "изменение материалов и геометрии фасада."
    ),
    "park_wide": (
        "ЗАПРЕЩЕНО: светильники на фасаде; LED-линии на стене; прожекторы на здании; "
        "изменение материалов и геометрии фасада."
    ),
}


def scenario_forbidden_line(scenario_id: str, application_prompt: str) -> str:
    if "ЗАПРЕЩЕНО" in application_prompt.upper():
        return ""
    return SCENARIO_FORBIDDEN.get(scenario_id, "")


def build_strict_client_router_prompt(scenario: dict, product: dict, has_product_front: bool, base: Path | None = None) -> str:
    sid = scenario["id"]
    app = scenario.get("application_prompt", "")
    forbidden = scenario_forbidden_line(sid, app)
    pname = product.get("short_name") or product.get("name", "")
    ies_block = build_ies_ai_prompt_block(ies_infos_for_product(product, base))
    product_line = (
        f"4) Product front — корпус {pname}, только эта форма светильника.\n"
        if has_product_front else ""
    )
    product_rules = (
        f"Тип светильника: {pname}. Корпус — как на product front. "
        "Не ставить свет на декоративные рейки, если сценарий этого не требует.\n"
        if has_product_front else f"Тип светильника: {pname}.\n"
    )
    return (
        "AI-визуализатор архитектурной подсветки NITEOS (клиентский режим).\n\n"
        "Изображения (строго):\n"
        "1) ИСХОДНОЕ ФОТО — единственный источник архитектуры. Сохранить здание 1:1: "
        "геометрия, этажность, окна, стекло, панели, цвет, деревянные рейки, пропорции. "
        "Ничего не менять, не перекрашивать, не добавлять новых элементов.\n"
        "2) Light plan — черновая подсказка зон. Не копировать линии и маркеры. При конфликте со сценарием — игнорировать.\n"
        "3) Style reference — ТОЛЬКО схема подсветки (какие зоны светятся, направление, характер). "
        "НЕ копировать здание, фасад, окна, дерево, небо и светильники с образца.\n"
        f"{product_line}\n"
        f"{ies_block}\n\n"
        f"Сценарий: «{scenario['name']}»\n"
        f"Правила: {app}\n"
        f"{forbidden}\n\n"
        f"{product_rules}"
        "Сделать одну реалистичную ночную визуализацию (синий час), 3000K.\n\n"
        "Обязательно:\n"
        "- Осветить всё здание на фото 1 слева направо строго по сценарию.\n"
        "- Добавить ТОЛЬКО свет и светильники сценария; архитектура остаётся как на фото 1.\n"
        "- Мягкий реалистичный свет, без мультяшности и плоских полос.\n\n"
        "Запрещено:\n"
        "- Менять фасад, материалы, цвет панелей, окна, декоративные элементы.\n"
        "- Брать с образца (img 3) элементы, не входящие в сценарий (другие типы света, другие зоны).\n"
        "- Люди, машины, новые вывески.\n\n"
        f"Итог: здание как на фото 1, ночь, подсветка строго по сценарию «{scenario['name']}»."
    )


def adapt_scenario_ai_prompt(prompt: str, base: Path) -> str:
    meta = read_project_meta(base)
    dealer_scenario_id = (meta.get("dealer_scenario_id") or "").strip()
    client_scenario_id = (meta.get("client_scenario_id") or "").strip()
    client_template_id = (meta.get("client_template_id") or "").strip()
    scenario_id = (dealer_scenario_id or client_scenario_id or client_template_id or "").strip()
    if not scenario_id:
        return prompt
    try:
        scenario = client_scenario_by_id(scenario_id)
        product_id = (
            meta.get("dealer_product_id")
            or meta.get("client_product_id")
            or product_id_for_scenario(scenario)
        )
        product = client_product_by_id(product_id)
    except HTTPException:
        return prompt
    has_product = (base / "references" / "product_front.png").exists()
    if dealer_scenario_id:
        dealer_block = build_dealer_scenario_prompt(scenario, product, base).strip()
        merged = f"{dealer_block}\n\n{prompt.strip()}\n"
        return patch_dealer_router_prompt(merged)
    return build_strict_client_router_prompt(scenario, product, has_product, base)


def patch_dealer_router_prompt(prompt: str) -> str:
    """Согласовать packager-промпт с dealer-сценарием: style ref = схема света, не только «качество»."""
    packager_style = (
        "Style ref — только качество: реализм, ночь, контраст, мягкий объемный свет. Архитектуру не копировать."
    )
    prompt = prompt.replace(f"Style: {packager_style}", f"Style: {CLIENT_STYLE_AI_BLOCK}")
    prompt = prompt.replace(
        "3) style reference.",
        "3) style reference — образец схемы подсветки (перенести логику света, не копировать здание).",
    )
    prompt = prompt.replace(
        "3) style reference, if provided.",
        "3) style reference — lighting scheme sample (transfer light logic, not building geometry).",
    )
    return prompt


def product_for_ies_filename(ies_name: str) -> dict | None:
    wanted = safe_name(ies_name).lower()
    for product in CLIENT_PRODUCTS:
        for filename in product.get("ies_files") or []:
            if safe_name(filename).lower() == wanted:
                return product
    blob = ies_name.upper()
    if "МАГИСТРАЛЬ" in blob or "MAGISTRAL" in blob:
        return client_product_by_id("magistral")
    if "NT-STEP" in blob or "NT-PARK" in blob or "PARK" in blob:
        return client_product_by_id("ntpark")
    if "NT-WAY" in blob or "X-RAY" in blob or "XRAY" in blob:
        return client_product_by_id("xray")
    return None


def build_render_ies_items(
    base: Path,
    ies_names: list[str],
    product_id: str = "",
    product_name: str = "",
) -> list[dict]:
    ies_dir = base / "ies_library"
    default_product = None
    if product_id:
        try:
            default_product = client_product_by_id(product_id)
        except HTTPException:
            default_product = None
    items: list[dict] = []
    for name in ies_names:
        ies_path = ies_dir / name
        if not ies_path.exists() and ies_dir.exists():
            for candidate in ies_dir.glob("*.ies"):
                if candidate.name.lower() == name.lower():
                    ies_path = candidate
                    name = candidate.name
                    break
        product = product_for_ies_filename(name) or default_product
        photo = None
        if ies_path.exists():
            photo = ies_catalog_photo(ies_path)
        if not photo:
            photo = product_photo_for_ies_name(name)
        items.append({
            "name": name,
            "relative_path": ies_path.name if ies_path.exists() else name,
            "has_photo": bool(photo and photo.exists()),
            "product_name": (product or {}).get("name") or product_name or infer_product_name_from_ies([name]),
            "product_short": (product or {}).get("short_name") or "",
            "product_id": (product or {}).get("id") or product_id or "",
        })
    return items


def _load_watermark_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def apply_niteos_watermark(final_path: Path) -> None:
    """Centered diagonal watermark `niteos.ru` (~40% width, 45°)."""
    if not final_path.exists():
        return
    try:
        with Image.open(final_path).convert("RGBA") as img:
            w, h = img.size
            text = "niteos.ru"
            target_w = max(48, int(w * 0.30))
            lo, hi = 8, max(48, int(min(w, h) * 0.55))
            font = _load_watermark_font(hi)
            probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            for _ in range(18):
                mid = (lo + hi) // 2
                font = _load_watermark_font(mid)
                bbox = probe.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                if tw < target_w:
                    lo = mid + 1
                else:
                    hi = mid - 1
            font = _load_watermark_font(max(8, hi))
            bbox = probe.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 12
            text_layer = Image.new("RGBA", (max(1, tw + pad * 2), max(1, th + pad * 2)), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            tx, ty = pad - bbox[0], pad - bbox[1]
            outline = (0, 0, 0, 90)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                text_draw.text((tx + dx, ty + dy), text, font=font, fill=outline)
            text_draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 128))
            if text_layer.size[0] != target_w:
                scale = target_w / max(1, text_layer.size[0])
                text_layer = text_layer.resize(
                    (target_w, max(1, int(text_layer.size[1] * scale))),
                    Image.Resampling.LANCZOS,
                )
            rotated = text_layer.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            x = (w - rotated.size[0]) // 2
            y = (h - rotated.size[1]) // 2
            overlay.paste(rotated, (x, y), rotated)
            out = Image.alpha_composite(img, overlay).convert("RGB")
            out.save(final_path, quality=95)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Watermark failed for %s: %s", final_path, exc)


def adapt_client_ai_prompt(prompt: str, base: Path) -> str:
    return adapt_scenario_ai_prompt(prompt, base)


def ies_infos_for_product(product: dict, base: Path | None = None) -> list:
    if base is not None:
        loaded = load_ies_infos_from_dir(base / "ies_library")
        if loaded:
            return loaded
    paths: list[Path] = []
    for filename in product.get("ies_files") or []:
        src = resolve_ies_source(filename)
        if src and src.exists():
            paths.append(src)
    if not paths:
        return []
    return _ies_infos_from_paths(paths)


def _ies_infos_from_paths(paths: list[Path]) -> list:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="niteos_ies_"))
    try:
        for src in paths:
            shutil.copy2(src, tmp / src.name)
        return load_ies_infos_from_dir(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_facade_mode(base: Path | None) -> str:
    if base is None:
        return "auto"
    mode_path = base / "facade_mode.txt"
    if mode_path.exists():
        return mode_path.read_text(encoding="utf-8", errors="ignore").strip() or "auto"
    return "auto"


def build_dealer_scenario_prompt(
    scenario: dict,
    product: dict,
    base: Path | None = None,
    facade_mode: str = "",
) -> str:
    mode = facade_mode.strip() or read_facade_mode(base)
    prompt = build_scenario_image_prompt(
        scenario["id"],
        fallback_app=scenario.get("application_prompt", ""),
        facade_mode=mode,
    )
    forbidden = scenario_forbidden_line(scenario["id"], scenario.get("application_prompt", ""))
    if forbidden:
        prompt = f"{prompt.rstrip()}\n\n{forbidden}\n"
    return append_facade_identity_lock(prompt)


def build_dealer_legacy_template_prompt(
    template_name: str,
    product: dict | None,
    base: Path | None = None,
    facade_mode: str = "",
) -> str:
    mode = facade_mode.strip() or read_facade_mode(base)
    product_line = ""
    if product:
        product_line = f"Продукт: {product['name']} ({product['short_name']}). "
    task = (
        f"{product_line}"
        f"Шаблон «{template_name}». Реалистичный ночной рендер архитектурной подсветки фасада "
        f"для презентации заказчику. Цвет: 5000К. Свет: по логике выбранного шаблона, "
        f"сохраняя геометрию здания с исходного фото."
    )
    return build_router_image_prompt(task=task, facade_mode=mode)


def apply_dealer_scenario(
    base: Path,
    scenario_id: str,
    product_id: str = "",
) -> dict:
    scenario = client_scenario_by_id(scenario_id)
    resolved_product_id = (product_id or "").strip() or product_id_for_scenario(scenario)
    product = client_product_by_id(resolved_product_id)

    ref = scenario_reference_path(scenario_id)
    if not ref:
        raise HTTPException(status_code=404, detail=f"Эталон сценария не найден: {scenario_id}")
    save_rgb(ref, base / "references" / "style_reference_target.png")

    export_id = product["export_id"]
    front = export_front_path(export_id)
    if front:
        save_rgb(front, base / "references" / "product_front.png")
    rules_path = export_dir(export_id) / "rules.txt"
    if rules_path.exists():
        shutil.copy2(rules_path, base / "references" / f"{export_id}_rules.txt")

    ies_dir = base / "ies_library"
    ies_dir.mkdir(parents=True, exist_ok=True)
    for old in ies_dir.iterdir():
        if old.is_file():
            old.unlink()
    saved_ies = []
    for filename in product.get("ies_files") or []:
        src = resolve_ies_source(filename)
        if not src:
            continue
        target = copy_ies_with_photo(src, ies_dir)
        saved_ies.append(target.name)

    prompt = build_dealer_scenario_prompt(scenario, product, base)
    (base / "prompt.txt").write_text(prompt, encoding="utf-8")
    (base / "facade_mode.txt").write_text(product.get("facade_mode") or "classic", encoding="utf-8")

    write_project_meta(base, {
        "dealer_scenario_id": scenario_id,
        "dealer_scenario_name": scenario.get("name"),
        "dealer_product_id": resolved_product_id,
        "dealer_product_name": product.get("name"),
        "dealer_legacy_ref": "",
        "style_name": ref.name,
        "has_style": True,
        "ies_count": len(saved_ies),
        "status": "scenario_applied",
    })
    append_pipeline_log(base, "dealer_scenario_applied", {
        "scenario_id": scenario_id,
        "scenario_name": scenario.get("name"),
        "product_id": resolved_product_id,
        "product_name": product.get("name"),
        "ies_files": saved_ies,
        "prompt": prompt,
    })
    return {"scenario": scenario, "product": product, "ies_files": saved_ies}


def prepare_image_for_vision(src: Path, max_side: int = 1600) -> Path:
    """Downscale large facades before vision calls (keeps original source untouched)."""
    if not src.exists():
        raise RuntimeError(f"Image not found: {src}")
    out = src.parent / f".vision_{src.stem}_{max_side}.jpg"
    try:
        if out.exists() and out.stat().st_mtime >= src.stat().st_mtime and out.stat().st_size > 0:
            return out
        with Image.open(src) as img:
            rgb = img.convert("RGB")
            w, h = rgb.size
            scale = min(1.0, max_side / max(w, h))
            if scale < 1.0:
                rgb = rgb.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            rgb.save(out, format="JPEG", quality=88, optimize=True)
            return out
    except Exception:
        return src


def list_auto_test_photos() -> list[dict]:
    VIZ_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    VIZ_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    # Some archive photos are ultra-high-res.
    Image.MAX_IMAGE_PIXELS = max(getattr(Image, "MAX_IMAGE_PIXELS", 0) or 0, 200_000_000)
    items = []
    for path in sorted(VIZ_EXAMPLES_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        thumb = VIZ_THUMBS_DIR / f"{path.stem}.jpg"
        try:
            if (not thumb.exists()) or thumb.stat().st_mtime < path.stat().st_mtime:
                with Image.open(path) as img:
                    rgb = img.convert("RGB")
                    rgb.thumbnail((320, 240), Image.Resampling.LANCZOS)
                    rgb.save(thumb, format="JPEG", quality=82, optimize=True)
        except Exception:
            thumb = path
        items.append({
            "id": path.stem,
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "preview_url": f"/api/auto-test-photos/{path.name}/thumb?t={int(path.stat().st_mtime)}",
            "url": f"/api/auto-test-photos/{path.name}?t={int(path.stat().st_mtime)}",
        })
    return items


def copy_auto_test_photo_to_project(base: Path, filename: str) -> Path:
    safe = Path(filename).name
    src = VIZ_EXAMPLES_DIR / safe
    if not src.exists() or src.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(status_code=404, detail=f"Test photo not found: {safe}")
    ensure_project_dirs(base)
    dest = base / "input" / "building.png"
    save_rgb(src, dest)
    mirror_to_library(dest, "source")
    write_project_meta(base, {
        "status": "source_uploaded",
        "source_name": safe,
        "has_source": True,
        "auto_test_photo": safe,
        "work_mode": "auto",
    })
    append_pipeline_log(base, "auto_test_photo_loaded", {"filename": safe})
    return dest


def auto_viz_ref_path(filename: str) -> Path:
    safe = Path(filename).name
    path = VIZ_EXAMPLES_DIR / safe
    if not path.exists() or path.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(status_code=404, detail=f"Viz reference not found: {safe}")
    return path


def build_auto_viz_mosaic(force: bool = False) -> Path:
    """Contact sheet of the 20 viz refs for classifier vision."""
    VIZ_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    mosaic = VIZ_THUMBS_DIR / "_auto_viz_mosaic.jpg"
    items = list_auto_test_photos()
    if not items:
        raise RuntimeError("Нет эталонов в assets/viz_examples/examples")
    newest = max((VIZ_EXAMPLES_DIR / it["filename"]).stat().st_mtime for it in items)
    if mosaic.exists() and not force and mosaic.stat().st_mtime >= newest and mosaic.stat().st_size > 0:
        return mosaic
    cols = 5
    cell_w, cell_h = 240, 170
    rows = (len(items) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (12, 14, 18))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    for idx, item in enumerate(items):
        r, c = divmod(idx, cols)
        x0, y0 = c * cell_w, r * cell_h
        thumb = VIZ_THUMBS_DIR / f"{Path(item['filename']).stem}.jpg"
        try:
            with Image.open(thumb if thumb.exists() else (VIZ_EXAMPLES_DIR / item["filename"])) as img:
                tile = img.convert("RGB")
                tile.thumbnail((cell_w - 8, cell_h - 28), Image.Resampling.LANCZOS)
                tx = x0 + (cell_w - tile.size[0]) // 2
                ty = y0 + 4
                canvas.paste(tile, (tx, ty))
        except Exception:
            draw.rectangle((x0 + 4, y0 + 4, x0 + cell_w - 4, y0 + cell_h - 28), outline=(80, 90, 100))
        label = f"{idx + 1}. {item['filename']}"
        draw.text((x0 + 6, y0 + cell_h - 22), label[:34], fill=(220, 228, 236), font=font)
    canvas.save(mosaic, format="JPEG", quality=85, optimize=True)
    return mosaic


def build_auto_viz_transfer_prompt(
    *,
    building_type: str = "",
    lighting_notes: list | None = None,
    reason: str = "",
    transfer_brief: dict | None = None,
) -> str:
    from scenario_router_prompts import PROMPT_GLOBAL_COVERAGE_QUALITY
    brief = transfer_brief or {}
    scheme = str(brief.get("lighting_scheme") or "").strip()
    transfer_ru = str(brief.get("transfer_prompt_ru") or "").strip()
    accents = brief.get("accent_zones") or lighting_notes or []
    if isinstance(accents, str):
        accents = [accents]
    accents = [str(x).strip() for x in accents if str(x).strip()]
    avoid = brief.get("do_not_copy_from_ref") or []
    if isinstance(avoid, str):
        avoid = [avoid]
    avoid = [str(x).strip() for x in avoid if str(x).strip()]

    parts = [
        "Ты — AI-визуализатор архитектурной подсветки NITEOS Concept Light.",
        "",
        "ИЗОБРАЖЕНИЯ:",
        "1) ИСХОДНЫЙ фасад — единственное здание финального кадра. Сохрани точную геометрию, сетку окон, материалы, пропорции, ракурс и все видимые крылья.",
        "2) ЭТАЛОН ночной подсветки — только характер света (куда ставятся акценты, ритм, контраст). НЕ копируй архитектуру, форму объёмов, окна и силуэт эталона.",
        "",
        "ЗАДАЧА: реалистичная ночная презентационная визуализация подсветки на базе изображения 1.",
        "Цвет света ≈ 5000К. Без пересветов, без текста, логотипов и водяных знаков.",
        "Фасадная схема должна покрывать весь видимый объём слева–направо и низ–середина–верх без тёмных «дыр».",
        "Запрещены уличные столбы, шаровые фонари и свет на дороге/тротуаре.",
    ]
    if building_type:
        parts.append(f"Тип здания по анализу: {building_type}.")
    if reason:
        parts.append(f"Почему выбран этот эталон: {reason}")
    if scheme:
        parts.append(f"Схема света с эталона (применить к архитектуре изображения 1): {scheme}")
    if accents:
        parts.append("Акцентные зоны: " + "; ".join(accents[:8]))
    if avoid:
        parts.append("Не переносить с эталона: " + "; ".join(avoid[:8]))
    if transfer_ru:
        parts.extend(["", "КОНКРЕТНОЕ ЗАДАНИЕ ПЕРЕНОСА:", transfer_ru])
    parts.extend(["", PROMPT_GLOBAL_COVERAGE_QUALITY, "", PROMPT_AUTO_FACADE_HARD_RULES])
    return "\n".join(parts)


def ensure_default_auto_ies(base: Path) -> list[str]:
    """Put a default facade IES set without binding to the 22 manual scenarios."""
    try:
        product = client_product_by_id("magistral")
    except HTTPException:
        return []
    ies_dir = base / "ies_library"
    ies_dir.mkdir(parents=True, exist_ok=True)
    for old in ies_dir.iterdir():
        if old.is_file():
            old.unlink()
    saved = []
    for filename in product.get("ies_files") or []:
        src = resolve_ies_source(filename)
        if not src:
            continue
        target = copy_ies_with_photo(src, ies_dir)
        saved.append(target.name)
    return saved


def classify_auto_viz_reference(base: Path, classifier_model: str = "") -> tuple[dict, dict]:
    source = base / "input" / "building.png"
    if not source.exists():
        raise RuntimeError("Сначала загрузите фото фасада в шаге 1")
    catalog = list_auto_test_photos()
    if not catalog:
        raise RuntimeError("Каталог 20 эталонов виз пуст")
    filenames = {item["filename"] for item in catalog}
    mosaic = build_auto_viz_mosaic()
    facade = analyze_facade_source(base)
    vision_source = prepare_image_for_vision(source, max_side=1600)
    prompt = (
        "You are an architectural lighting consultant for NITEOS.\n"
        "Image 1 = CURRENT source facade that MUST remain the final building.\n"
        "Image 2 = mosaic of 20 night lighting viz examples (each tile labeled with its filename).\n"
        "Pick the single best example whose LIGHTING LANGUAGE fits Image 1 architecture.\n\n"
        "Priority order:\n"
        "1) Similar building class (classic masonry / modern glass / tower / wide wing / church / retail).\n"
        "2) Compatible camera / massing (corner vs frontal, tall vs wide).\n"
        "3) Full-facade architectural lighting (not road poles).\n"
        "Never pick a look that would force reshaping Image 1 into another building.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "filename": "exact_filename_from_catalog",\n'
        '  "confidence": 0.0,\n'
        '  "building_type": "short label of Image 1",\n'
        '  "reason": "1-2 sentences why this look fits Image 1",\n'
        '  "lighting_notes": ["how light is placed on the chosen example"],\n'
        '  "lighting_scheme": "short scheme label, e.g. cornice+vertical piers"\n'
        "}\n\n"
        "Rules:\n"
        "- filename MUST be one of the catalog filenames.\n"
        "- Prefer continuity of light across the whole visible facade height/width.\n"
        "- Do not invent filenames.\n\n"
        f"Local facade heuristics: {json.dumps(facade, ensure_ascii=False)}\n"
        f"Catalog filenames: {json.dumps([i['filename'] for i in catalog], ensure_ascii=False)}"
    )
    model = (classifier_model or AUTO_SCENARIO_CLASSIFIER_MODEL).strip()
    try:
        result, api_log = call_routerai_vision_json(prompt, [vision_source, mosaic], model=model)
        api_log["kind"] = "auto_viz_classify"
    except Exception as error:
        result = {
            "filename": catalog[0]["filename"],
            "confidence": 0.25,
            "building_type": facade.get("composition") or "unknown",
            "reason": "Fallback: first viz example (classifier unavailable).",
            "lighting_notes": [],
            "lighting_scheme": "",
            "fallback": True,
        }
        api_log = {"kind": "auto_viz_classify", "fallback": True, "error": str(error)[:800], "model": model}
    result["facade"] = facade
    fname = str(result.get("filename") or "").strip()
    if fname not in filenames:
        stem_map = {Path(n).stem: n for n in filenames}
        if Path(fname).stem in stem_map:
            fname = stem_map[Path(fname).stem]
            result["filename"] = fname
        else:
            result = {
                "filename": catalog[0]["filename"],
                "confidence": 0.2,
                "building_type": result.get("building_type") or facade.get("composition") or "unknown",
                "reason": "Fallback after invalid classifier filename.",
                "lighting_notes": result.get("lighting_notes") or [],
                "lighting_scheme": result.get("lighting_scheme") or "",
                "fallback": True,
                "vision_raw_filename": fname,
                "facade": facade,
            }
            api_log["invalid_filename"] = fname
    try:
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence") or 0)))
    except (TypeError, ValueError):
        result["confidence"] = 0.0
    return result, api_log


def build_auto_transfer_brief(base: Path, viz_filename: str, classifier_model: str = "") -> tuple[dict, dict]:
    """Compare source + chosen viz and produce concrete lighting-transfer text for the render prompt."""
    source = base / "input" / "building.png"
    ref = auto_viz_ref_path(viz_filename)
    vision_source = prepare_image_for_vision(source, max_side=1600)
    vision_ref = prepare_image_for_vision(ref, max_side=1400)
    prompt = (
        "You plan architectural lighting transfer for NITEOS.\n"
        "Image 1 = SOURCE facade that must keep identity.\n"
        "Image 2 = LIGHTING reference look.\n"
        "Describe how to light Image 1 using ONLY the lighting ideas from Image 2.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "lighting_scheme": "short scheme",\n'
        '  "accent_zones": ["zone on Image 1 architecture"],\n'
        '  "do_not_copy_from_ref": ["what must not be copied from Image 2"],\n'
        '  "transfer_prompt_ru": "one Russian paragraph: concrete night lighting task for Image 1, 5000K, full facade coverage, no street poles"\n'
        "}\n"
        "transfer_prompt_ru must explicitly say: keep geometry of photo 1, adapt light of photo 2 to its cornices/windows/pilasters."
    )
    model = (classifier_model or AUTO_SCENARIO_CLASSIFIER_MODEL).strip()
    try:
        result, api_log = call_routerai_vision_json(prompt, [vision_source, vision_ref], model=model)
        api_log["kind"] = "auto_viz_transfer_brief"
        return result, api_log
    except Exception as error:
        return {}, {"kind": "auto_viz_transfer_brief", "fallback": True, "error": str(error)[:800], "model": model}


def apply_auto_viz_reference(
    base: Path,
    filename: str,
    *,
    classification: dict | None = None,
    transfer_brief: dict | None = None,
) -> dict:
    src = auto_viz_ref_path(filename)
    ensure_project_dirs(base)
    refs = base / "references"
    refs.mkdir(parents=True, exist_ok=True)
    save_rgb(src, refs / "style_reference_target.png")
    classification = classification or {}
    prompt = build_auto_viz_transfer_prompt(
        building_type=str(classification.get("building_type") or ""),
        lighting_notes=list(classification.get("lighting_notes") or []),
        reason=str(classification.get("reason") or ""),
        transfer_brief=transfer_brief or {
            "lighting_scheme": classification.get("lighting_scheme") or "",
            "accent_zones": classification.get("lighting_notes") or [],
        },
    )
    (base / "prompt.txt").write_text(prompt, encoding="utf-8")
    (base / "facade_mode.txt").write_text("auto", encoding="utf-8")
    saved_ies = ensure_default_auto_ies(base)
    write_project_meta(base, {
        "work_mode": "auto",
        "auto_viz_ref": Path(filename).name,
        "dealer_scenario_id": "",
        "dealer_scenario_name": f"Авто-эталон виз: {Path(filename).name}",
        "dealer_product_id": "magistral",
        "dealer_product_name": "MAGISTRAL",
        "dealer_legacy_ref": "",
        "style_name": Path(filename).name,
        "has_style": True,
        "ies_count": len(saved_ies),
        "status": "auto_viz_applied",
    })
    append_pipeline_log(base, "auto_viz_ref_applied", {
        "filename": Path(filename).name,
        "ies_files": saved_ies,
        "prompt_chars": len(prompt),
        "has_transfer_brief": bool(transfer_brief),
    })
    return {"filename": Path(filename).name, "ies_files": saved_ies, "prompt": prompt}


def run_auto_viz_pipeline(
    base: Path,
    *,
    router_model: str = "",
    classifier_model: str = "",
    viz_filename: str = "",
    generate: bool = True,
) -> dict:
    """Auto catalog = 20 viz examples. Pick one as lighting look, then optionally generate."""
    api_log: dict = {}
    brief_log: dict = {}
    transfer_brief: dict = {}
    if viz_filename.strip():
        classification = {
            "filename": Path(viz_filename).name,
            "confidence": 1.0,
            "building_type": "manual_pick",
            "reason": "Пользователь выбрал эталон из 20 вручную.",
            "lighting_notes": [],
            "lighting_scheme": "",
            "fallback": False,
        }
    else:
        classification, api_log = classify_auto_viz_reference(base, classifier_model=classifier_model)
        append_pipeline_log(base, "auto_viz_classify", {"classification": classification, "api": api_log})
    fname = str(classification.get("filename") or "").strip()
    transfer_brief, brief_log = build_auto_transfer_brief(base, fname, classifier_model=classifier_model)
    if brief_log:
        append_pipeline_log(base, "auto_viz_transfer_brief", {"brief": transfer_brief, "api": brief_log})
    applied = apply_auto_viz_reference(
        base,
        fname,
        classification=classification,
        transfer_brief=transfer_brief,
    )
    write_project_meta(base, {
        "auto_viz": {
            "filename": fname,
            "confidence": classification.get("confidence"),
            "reason": classification.get("reason") or "",
            "lighting_scheme": (transfer_brief or {}).get("lighting_scheme") or classification.get("lighting_scheme") or "",
            "fallback": bool(classification.get("fallback") or api_log.get("fallback")),
            "updated_at": now_iso(),
        }
    })
    # Use transfer prompt as-is (identity-locked); only append hard rules via prepare.
    preview = prepare_agent_render_prompt(base, router_model=router_model)
    (base / "prompt.txt").write_text(preview["base_prompt"], encoding="utf-8")
    out_dir = base / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "auto_render_prompt_preview.txt").write_text(preview["render_prompt"], encoding="utf-8")
    final_path = None
    if generate:
        final_path = render_project(base, router_model=router_model, review_profile="economic")
    return {
        "classification": classification,
        "api_log": api_log,
        "brief_log": brief_log,
        "transfer_brief": transfer_brief,
        "applied": applied,
        "preview": preview,
        "final": str(final_path) if final_path else "",
        "generated": bool(generate and final_path),
    }


def dealer_scenario_catalog_for_classifier(*, facade_only: bool = True) -> list[dict]:
    items = []
    for scenario in catalog_client_scenarios():
        sid = scenario["id"]
        category = scenario.get("category") or ""
        if facade_only and (category == "ground" or sid.startswith("park_")):
            continue
        hint = (scenario.get("application_prompt") or scenario.get("description") or "").strip()
        items.append({
            "id": sid,
            "name": scenario.get("name") or sid,
            "category": category,
            "hint": hint[:280],
        })
    return items


def heuristic_scenario_pick(facade: dict, catalog: list[dict]) -> dict:
    ids = {item["id"] for item in catalog}
    composition = str(facade.get("composition") or "")
    if composition == "tall_facade":
        preferred = [
            "shopping_center_vertical_lines",
            "linear_vertical",
            "administrative_horizontal_lines",
            "linear_mix_full",
        ]
    elif composition == "wide_facade":
        preferred = [
            "business_center_linear_cornice",
            "linear_horizontal",
            "linear_cornice",
            "linear_mix_full",
        ]
    else:
        preferred = [
            "linear_mix_full",
            "residential_combined",
            "business_center_linear_cornice",
            "hotel_combined",
        ]
    for sid in preferred:
        if sid in ids:
            return {
                "scenario_id": sid,
                "confidence": 0.35,
                "building_type": composition or "unknown",
                "reason": "Local facade heuristic fallback (vision classifier unavailable).",
                "facade_notes": list(facade.get("tags") or []),
                "fallback": True,
            }
    first = catalog[0]["id"] if catalog else "linear_mix_full"
    return {
        "scenario_id": first,
        "confidence": 0.2,
        "building_type": composition or "unknown",
        "reason": "Default catalog fallback.",
        "facade_notes": list(facade.get("tags") or []),
        "fallback": True,
    }


def classify_scenario_from_facade(base: Path, classifier_model: str = "") -> tuple[dict, dict]:
    source = base / "input" / "building.png"
    if not source.exists():
        raise RuntimeError("Сначала загрузите фото фасада")
    catalog = dealer_scenario_catalog_for_classifier(facade_only=True)
    if not catalog:
        raise RuntimeError("Каталог сценариев пуст")
    facade = analyze_facade_source(base)
    catalog_ids = {item["id"] for item in catalog}
    prompt = (
        "You are an architectural lighting consultant for NITEOS Concept Light.\n"
        "Look ONLY at the CURRENT facade source photo and choose the single best FACADE lighting scenario from the catalog.\n"
        "Ignore previous project history, old night renders, and style-reference gallery images.\n\n"
        "Return JSON only, without markdown:\n"
        "{\n"
        '  "scenario_id": "exact_id_from_catalog",\n'
        '  "confidence": 0.0,\n'
        '  "building_type": "short label",\n'
        '  "reason": "1-2 sentences why this template fits THIS photo",\n'
        '  "facade_notes": ["short note"]\n'
        "}\n\n"
        "Rules:\n"
        "- scenario_id MUST be exactly one catalog id.\n"
        "- Choose facade architectural lighting (linear / projector / wash). Never choose street/park pole schemes.\n"
        "- Prefer full visible-facade coverage, continuous vertical rhythm through ALL floor bands, no dark leftover mid-floors.\n"
        "- Prefer building-type match (office, historic, residential, hotel, church, retail) when clear.\n"
        "- If the photo shows existing street lamps, DO NOT pick them as the lighting concept — they are context, not the project schema.\n"
        "- Do not invent ids.\n\n"
        f"Local facade heuristics (optional prior): {json.dumps(facade, ensure_ascii=False)}\n\n"
        f"Catalog: {json.dumps(catalog, ensure_ascii=False)}"
    )
    model = (classifier_model or AUTO_SCENARIO_CLASSIFIER_MODEL).strip()
    vision_path = prepare_image_for_vision(source, max_side=1600)
    try:
        result, api_log = call_routerai_vision_json(prompt, [vision_path], model=model)
        api_log["kind"] = "auto_scenario_classify"
        api_log["vision_source"] = vision_path.name
    except Exception as error:
        result = heuristic_scenario_pick(facade, catalog)
        api_log = {
            "kind": "auto_scenario_classify",
            "fallback": True,
            "error": str(error)[:800],
            "model": model,
        }
    sid = str(result.get("scenario_id") or "").strip()
    if sid not in catalog_ids:
        fallback = heuristic_scenario_pick(facade, catalog)
        result = {**fallback, "vision_raw_scenario_id": sid}
        api_log["invalid_scenario_id"] = sid
    result["facade"] = facade
    conf = result.get("confidence")
    try:
        result["confidence"] = max(0.0, min(1.0, float(conf)))
    except (TypeError, ValueError):
        result["confidence"] = 0.0
    return result, api_log


def run_auto_scenario_pipeline(
    base: Path,
    *,
    router_model: str = "",
    classifier_model: str = "",
    apply: bool = True,
) -> dict:
    classification, api_log = classify_scenario_from_facade(base, classifier_model=classifier_model)
    append_pipeline_log(base, "auto_scenario_classify", {
        "classification": classification,
        "api": api_log,
    })
    scenario_id = str(classification.get("scenario_id") or "").strip()
    applied = None
    preview = None
    if apply and scenario_id:
        applied = apply_dealer_scenario(base, scenario_id)
        preview = prepare_agent_render_prompt(base, router_model=router_model)
        # Persist the template prompt; generation still rebuilds placement/learning on render.
        (base / "prompt.txt").write_text(preview["base_prompt"], encoding="utf-8")
        out_dir = base / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "auto_render_prompt_preview.txt").write_text(
            preview["render_prompt"],
            encoding="utf-8",
        )
        write_project_meta(base, {
            "work_mode": "auto",
            "auto_scenario": {
                "scenario_id": scenario_id,
                "confidence": classification.get("confidence"),
                "building_type": classification.get("building_type") or "",
                "reason": classification.get("reason") or "",
                "facade_notes": classification.get("facade_notes") or [],
                "fallback": bool(classification.get("fallback") or api_log.get("fallback")),
                "updated_at": now_iso(),
            },
            "last_placement_plan": preview.get("placement_plan") or {},
            "learning_guidance": preview.get("learning_guidance") or {},
        })
        append_pipeline_log(base, "auto_scenario_applied", {
            "scenario_id": scenario_id,
            "prompt_chars": preview.get("prompt_chars"),
            "placement_strategy": (preview.get("placement_plan") or {}).get("strategy"),
        })
    return {
        "classification": classification,
        "api_log": api_log,
        "applied": applied,
        "preview": preview,
    }


def sync_scenarios_to_style_library() -> int:
    dest_dir = STYLE_LIBRARY_DIR / "scenarios"
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for scenario in ALL_CLIENT_SCENARIOS:
        ref = scenario_reference_path(scenario["id"])
        if not ref:
            continue
        target = dest_dir / f"{scenario['id']}.png"
        shutil.copy2(ref, target)
        prompt_path = SCENARIO_PROMPTS_DIR / f"{scenario['id']}.txt"
        if prompt_path.exists():
            shutil.copy2(prompt_path, dest_dir / f"{scenario['id']}.txt")
        count += 1
    return count


def read_export_text(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "cp866"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def export_dir(export_id: str) -> Path:
    return EXPORTS_FIXTURES_DIR / export_id


def export_legacy_reference_path(export_id: str) -> Path | None:
    ref = export_dir(export_id) / "reference-application.png"
    return ref if ref.exists() else None


def export_front_path(export_id: str) -> Path | None:
    front = export_dir(export_id) / "front.png"
    return front if front.exists() else None


def export_prompt_test(export_id: str) -> str:
    return read_export_text(export_dir(export_id) / "prompt-test-on-photo.txt")


def export_rules(export_id: str) -> str:
    return read_export_text(export_dir(export_id) / "rules.txt")


def scenario_reference_path(scenario_id: str) -> Path | None:
    path = SCENARIOS_DIR / f"{scenario_id}.png"
    if path.exists():
        return path
    for export_id in ("magistral-v3-ai-70", "x-ray", "nt-park-step"):
        legacy = export_dir(export_id) / "references" / f"{scenario_id}.png"
        if legacy.exists():
            return legacy
    return None


CLIENT_PRODUCTS: list[dict] = [
    {
        "id": "magistral",
        "export_id": "magistral-v3-ai-70",
        "name": "MAGISTRAL v 3.0 AI 70",
        "short_name": "MAGISTRAL",
        "description": "Линейный LED-светильник для фасада — контуры, пояса, вертикали.",
        "facade_mode": "classic",
        "ies_files": [IES_LINEAR],
    },
    {
        "id": "xray",
        "export_id": "x-ray",
        "name": "X-RAY ARCH",
        "short_name": "X-RAY",
        "description": "Компактный фасадный прожектор — заливка и акценты на стене.",
        "facade_mode": "classic",
        "ies_files": [IES_XRAY],
    },
    {
        "id": "ntpark",
        "export_id": "nt-park-step",
        "name": "NT-park STEP",
        "short_name": "NT-park",
        "description": "Парковый фонарь-столб у дороги перед зданием.",
        "facade_mode": "classic",
        "ies_files": [IES_NT_PARK],
    },
]


def product_photo_for_ies_name(ies_name: str) -> Path | None:
    wanted = safe_name(ies_name).lower()
    for product in CLIENT_PRODUCTS:
        for ies_file in product.get("ies_files") or []:
            if safe_name(ies_file).lower() == wanted:
                return export_front_path(product["export_id"])
    blob = ies_name.upper()
    if "МАГИСТРАЛЬ" in blob or "MAGISTRAL" in blob:
        return export_front_path("magistral-v3-ai-70")
    if "NT-WAY" in blob or "X-RAY" in blob or "XRAY" in blob:
        return export_front_path("x-ray")
    if "NT-STEP" in blob or "NT-PARK" in blob or "PARK" in blob:
        return export_front_path("nt-park-step")
    return None


def sync_ies_catalog_photos() -> int:
    count = 0
    if not IES_LIBRARY_DIR.exists():
        return count
    for ies in IES_LIBRARY_DIR.rglob("*.ies"):
        if ies_photo_path(ies):
            continue
        src = product_photo_for_ies_name(ies.name)
        if not src or not src.exists():
            continue
        ext = src.suffix if src.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ".png"
        target = ies.with_suffix(ext)
        if not target.exists():
            shutil.copy2(src, target)
            count += 1
    return count


def bootstrap_ies_catalog() -> int:
    """Гарантирует ровно 3 IES + фото в каталоге из assets/ies-catalog (в репозитории)."""
    if not IES_CATALOG_DIR.exists():
        return 0
    IES_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    bundle_ies = sorted(IES_CATALOG_DIR.glob("*.ies"))
    if not bundle_ies:
        return 0
    allowed = set()
    for src in bundle_ies:
        allowed.add(src.name)
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            photo = src.with_suffix(ext)
            if photo.exists():
                allowed.add(photo.name)
    for existing in list(IES_LIBRARY_DIR.iterdir()):
        if existing.is_file() and existing.name not in allowed:
            existing.unlink(missing_ok=True)
    count = 0
    for src in bundle_ies:
        copy_unique(src, IES_LIBRARY_DIR, src.name)
        count += 1
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            photo = src.with_suffix(ext)
            if photo.exists():
                copy_unique(photo, IES_LIBRARY_DIR, photo.name)
                break
    return count


LEGACY_CATALOG_SCENARIO_ORDER: list[str] = [
    "linear_mix_full",
    "xray_columns",
    "linear_cornice",
    "xray_wash",
    "linear_mix_cv",
    "linear_mix_ch",
    "linear_mix_hv",
]

DEALER_CATALOG_SCENARIO_ORDER: list[str] = LEGACY_CATALOG_SCENARIO_ORDER + list(CATALOG_SCENARIO_ORDER)

CLIENT_SCENARIOS: list[dict] = [
    {"id": "linear_mix_full", "category": "catalog", "name": "Контурная подсветка",
     "description": "Линейный контур по архитектурным линиям фасада.", "application_prompt": ""},
    {"id": "xray_columns", "category": "catalog", "name": "Прожекторы между окнами",
     "description": "Вертикальные акценты в простенках между окнами.", "application_prompt": ""},
    {"id": "linear_cornice", "category": "catalog", "name": "Прожекторы верх-вниз",
     "description": "Направленные лучи вверх и вниз между окнами.", "application_prompt": ""},
    {"id": "xray_wash", "category": "catalog", "name": "Заливающая линейными",
     "description": "Мягкая заливка плоскостей линейными светильниками.", "application_prompt": ""},
    {"id": "linear_mix_cv", "category": "catalog", "name": "Контурная + прожекторы",
     "description": "Контур по линиям фасада и прожекторные акценты.", "application_prompt": ""},
    {"id": "linear_mix_ch", "category": "catalog", "name": "Линейная + прожекторы",
     "description": "Горизонтальные линейные элементы и прожекторные акценты.", "application_prompt": ""},
    {"id": "linear_mix_hv", "category": "catalog", "name": "Заливающая + контурная + прожекторы",
     "description": "Три слоя: заливка, контур и акценты.", "application_prompt": ""},
    {"id": "business_center_linear_cornice", "category": "catalog", "name": "Бизнес-центр: горизонтали + кровля",
     "description": "Линейные полосы на каждом этаже и двойной контур кровли.", "application_prompt": ""},
    {"id": "administrative_horizontal_lines", "category": "catalog", "name": "Административное: пояса + вертикали",
     "description": "Три горизонтальных пояса и аплайты на пилястрах.", "application_prompt": ""},
    {"id": "shopping_center_vertical_lines", "category": "catalog", "name": "ТЦ: вертикали на крыльях",
     "description": "Вертикальные аплайты на камне, контур кровли, свечение витражей.", "application_prompt": ""},
    {"id": "small_office_projectors", "category": "catalog", "name": "Офис: вертикальные прожекторы",
     "description": "Аплайты в простенках на всех этажах и контур кровли.", "application_prompt": ""},
    {"id": "historic_building_projectors", "category": "catalog", "name": "Историческое: градировка",
     "description": "Аплайты с цоколя и карнизов по всему угловому фасаду.", "application_prompt": ""},
    {"id": "residential_combined", "category": "catalog", "name": "Жилой дом: балконы",
     "description": "Вертикали между балконами и линейный свет карнизов.", "application_prompt": ""},
    {"id": "hotel_combined", "category": "catalog", "name": "Отель: контур + вход",
     "description": "Контур кровли, вертикали, подсветка козырька и цоколя.", "application_prompt": ""},
    {"id": "restaurant_projectors_columns", "category": "catalog", "name": "Ресторан: бра верх-низ",
     "description": "Светильники верх-низ на каждом простенке между арками.", "application_prompt": ""},
    {"id": "industrial_vertical_wash", "category": "catalog", "name": "Индустриальное: верх-низ",
     "description": "Бра верх-низ по ритму панелей между окнами.", "application_prompt": ""},
    {"id": "warehouse_linear_contour", "category": "catalog", "name": "Склад: кровля + ворота",
     "description": "Линейный контур кровли и прожекторы над каждыми воротами.", "application_prompt": ""},
    {"id": "car_showroom_linear_contour", "category": "catalog", "name": "Автосалон: контур кровли",
     "description": "Одна линейная полоса по верхнему периметру стеклянного объёма.", "application_prompt": ""},
    {"id": "sports_complex_projectors_wash", "category": "catalog", "name": "Спорткомплекс: верх-низ + навес",
     "description": "Бра на швах фасада и даунлайт под навесом витражей.", "application_prompt": ""},
    {"id": "theater_projectors_columns", "category": "catalog", "name": "Театр: колонны + фронтон",
     "description": "Аплайты у колонн портика и подсветка фронтона.", "application_prompt": ""},
    {"id": "university_combined", "category": "catalog", "name": "Университет: контур + портал",
     "description": "Контур карниза, вертикали снизу, акцент входа.", "application_prompt": ""},
    {"id": "church_projectors_architecture", "category": "catalog", "name": "Храм: аплайты по ярусам",
     "description": "Подсветка пилястр, арок, карнизов и барабанов куполов.", "application_prompt": ""},
]

# Скрытые сценарии — только для совместимости старых проектов, не в каталоге дилера.
CLIENT_SCENARIOS_HIDDEN: list[dict] = [
    {"id": "linear_horizontal", "category": "linear", "name": "Только горизонтали",
     "description": "Пояса между рядами окон на каждом этаже.",
     "application_prompt": "Только горизонтальные линии между рядами окон на каждом этаже. Без линии по карнизу и без вертикалей."},
    {"id": "linear_vertical", "category": "linear", "name": "Только вертикали",
     "description": "Линии вверх по простенкам между окнами.",
     "application_prompt": "Только вертикальные линии по простенкам между окнами, на всю высоту фасада. Без горизонталей и без карниза."},
    {"id": "linear_top_bottom", "category": "linear", "name": "Верх и низ",
     "description": "Карниз + линия на цоколе.",
     "application_prompt": "Линия по карнизу и отдельная линия по цоколю или первому этажу. Средние этажи без линий."},
    {"id": "xray_openings", "category": "projector", "name": "Над проёмами",
     "description": "Акцент на вход и витражи.",
     "application_prompt": "Светильники над входной группой, витражами и ключевыми окнами. Остальной фасад темнее."},
    {"id": "xray_graze", "category": "projector", "name": "Скользящий свет",
     "description": "Свет по фактуре кирпича или камня.",
     "application_prompt": "Плоский скользящий свет по фактуре фасада, подчёркивает рельеф и текстуру."},
    {"id": "park_row", "category": "ground", "name": "Ряд фонарей",
     "description": "5–7 столбов вдоль дороги перед фасадом.",
     "application_prompt": "Ровный ряд столбов на тротуаре перед зданием, шаг ~8 м. Не на стене. Пятна на дороге и мягкий свет на цоколь."},
    {"id": "park_entrance", "category": "ground", "name": "Усиление у входа",
     "description": "Больше столбов у парадного входа.",
     "application_prompt": "Ряд столбов вдоль фасада плюс дополнительные столбы плотнее у главного входа и витражей."},
    {"id": "park_wide", "category": "ground", "name": "Редкий шаг",
     "description": "3–4 столба на большом расстоянии.",
     "application_prompt": "Только 3–4 столба с шагом 12–15 м, крупные мягкие пятна, спокойный ритм. Не на фасаде."},
]

ALL_CLIENT_SCENARIOS: list[dict] = CLIENT_SCENARIOS + CLIENT_SCENARIOS_HIDDEN

SCENARIO_PROMPTS_DIR = SCENARIOS_DIR / "prompts"


def scenario_prompt_from_file(scenario_id: str) -> str | None:
    path = SCENARIO_PROMPTS_DIR / f"{scenario_id}.txt"
    if not path.exists():
        return None
    text = read_export_text(path).strip()
    match = re.search(
        r"ПРАВИЛА ИСПОЛЬЗОВАНИЯ СВЕТИЛЬНИКА:\s*\n(.+?)(?:\n\nВАЖНО:|\Z)",
        text,
        re.S,
    )
    if match:
        return match.group(1).strip()
    if text and not text.startswith("Файл:"):
        return text
    return None


SCENARIO_DEFAULT_PRODUCT = {
    "linear": "magistral",
    "projector": "xray",
    "ground": "ntpark",
    "catalog": "magistral",
}

SCENARIO_PRODUCT_ID: dict[str, str] = {
    **CATALOG_PRODUCT_ID,
    "linear_mix_full": "magistral",
    "xray_columns": "xray",
    "linear_cornice": "xray",
    "xray_wash": "magistral",
    "linear_mix_cv": "magistral",
    "linear_mix_ch": "magistral",
    "linear_mix_hv": "magistral",
}


def product_id_for_scenario(scenario: dict) -> str:
    sid = scenario.get("id", "")
    if sid in SCENARIO_PRODUCT_ID:
        return SCENARIO_PRODUCT_ID[sid]
    return SCENARIO_DEFAULT_PRODUCT.get(scenario.get("category", ""), "magistral")


def catalog_client_scenarios() -> list[dict]:
    by_id = {item["id"]: item for item in CLIENT_SCENARIOS}
    return [by_id[sid] for sid in DEALER_CATALOG_SCENARIO_ORDER if sid in by_id]


for _scenario in ALL_CLIENT_SCENARIOS:
    _loaded = scenario_prompt_from_file(_scenario["id"])
    if _loaded:
        _scenario["application_prompt"] = _loaded

SCENARIO_CATEGORY_LABELS = {
    "catalog": "Варианты подсветки",
    "linear": "Линейные схемы",
    "projector": "Прожекторные схемы",
    "ground": "Наземные схемы",
}

# Legacy-шаблоны скрыты из каталога дилера.
DEALER_LEGACY_STYLE_FILES: list[str] = []
# DEALER_LEGACY_STYLE_FILES = ["1.jpg", "2.png", "3.jpg", "4.jpg"]

DEALER_LEGACY_TEMPLATE_BINDINGS: dict[str, dict] = {
    # Legacy-шаблоны — быстрые пресеты. Привязываем IES/продукт, чтобы фотометрия переносилась в проект.
    "legacy_1": {"product_id": "magistral", "ies_files": [IES_LINEAR]},
    "legacy_2": {"product_id": "xray", "ies_files": [IES_XRAY]},
    "legacy_3": {"product_id": "ntpark", "ies_files": [IES_NT_PARK]},
    "legacy_4": {"product_id": "magistral", "ies_files": [IES_LINEAR]},
}


def ensure_legacy_style_refs() -> int:
    count = 0
    for name in DEALER_LEGACY_STYLE_FILES:
        target = STYLE_LIBRARY_DIR / name
        if target.exists():
            count += 1
            continue
        src = ROOT / "examples" / "style_references" / name
        if not src.exists():
            continue
        shutil.copy2(src, target)
        count += 1
    return count


try:
    sync_scenarios_to_style_library()
    ensure_legacy_style_refs()
    bootstrap_ies_catalog()
    import_existing_to_library()
    sync_ies_catalog_photos()
except Exception:
    pass


def client_product_by_id(product_id: str) -> dict:
    for item in CLIENT_PRODUCTS:
        if item["id"] == product_id:
            return item
    raise HTTPException(status_code=404, detail="Product not found")


def client_scenario_by_id(scenario_id: str) -> dict:
    for item in ALL_CLIENT_SCENARIOS:
        if item["id"] == scenario_id:
            return item
    raise HTTPException(status_code=404, detail="Scenario not found")


def build_product_instruction(product: dict) -> str:
    export_id = product["export_id"]
    parts = [f"Продукт: {product['name']} ({product['short_name']})."]
    parts.append(export_prompt_test(export_id) or f"Корпус и крепление — как на product front ({product['short_name']}).")
    rules = export_rules(export_id)
    if rules:
        parts.append(f"Правила продукта:\n{rules}")
    return "\n".join(parts)


def build_client_render_prompt(
    product: dict,
    scenario: dict,
    prompt_override: str = "",
    base: Path | None = None,
) -> str:
    mode = read_facade_mode(base)
    if prompt_override.strip():
        return build_router_image_prompt(task=prompt_override.strip(), facade_mode=mode)
    return build_scenario_image_prompt(
        scenario["id"],
        fallback_app=scenario.get("application_prompt", ""),
        facade_mode=mode,
    )


def client_product_public(item: dict) -> dict:
    front = export_front_path(item["export_id"])
    return {
        "id": item["id"],
        "export_id": item["export_id"],
        "name": item["name"],
        "short_name": item["short_name"],
        "description": item["description"],
        "has_preview": front is not None,
    }


def client_scenario_public(item: dict) -> dict:
    ref = scenario_reference_path(item["id"])
    return {
        "id": item["id"],
        "category": item["category"],
        "category_label": SCENARIO_CATEGORY_LABELS.get(item["category"], item["category"]),
        "name": item["name"],
        "description": item["description"],
        "has_preview": ref is not None,
        "reference_path": f"exports/mvp-fixtures/scenarios/{item['id']}.png",
        "prompt_preview": item["application_prompt"][:160],
        "prompt_updated": scenario_prompt_updated(item["id"]),
    }


def apply_client_selection(
    base: Path,
    product_id: str,
    scenario_id: str,
    prompt_override: str = "",
) -> dict:
    product = client_product_by_id(product_id)
    scenario = client_scenario_by_id(scenario_id)
    prompt = build_client_render_prompt(product, scenario, prompt_override, base)
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is empty")

    (base / "prompt.txt").write_text(prompt, encoding="utf-8")
    (base / "facade_mode.txt").write_text(product.get("facade_mode") or "classic", encoding="utf-8")

    export_id = product["export_id"]
    has_style = False
    style_name = ""
    ref = scenario_reference_path(scenario_id)
    if ref:
        save_rgb(ref, base / "references" / "style_reference_target.png")
        has_style = True
        style_name = ref.name
    front = export_front_path(export_id)
    if front:
        save_rgb(front, base / "references" / "product_front.png")
    rules_path = export_dir(export_id) / "rules.txt"
    if rules_path.exists():
        shutil.copy2(rules_path, base / "references" / f"{export_id}_rules.txt")

    ies_dir = base / "ies_library"
    ies_dir.mkdir(parents=True, exist_ok=True)
    for old in ies_dir.glob("*.ies"):
        old.unlink()
    saved_ies = []
    for filename in product.get("ies_files") or []:
        src = resolve_ies_source(filename)
        if not src:
            continue
        target = ies_dir / safe_name(src.name)
        shutil.copy2(src, target)
        saved_ies.append(target.name)

    write_project_meta(base, {
        "client_product_id": product_id,
        "client_product_name": product.get("name"),
        "client_scenario_id": scenario_id,
        "client_scenario_name": scenario.get("name"),
        "client_export_id": export_id,
        "client_template_id": scenario_id,
        "client_template_name": scenario.get("name"),
        "style_name": style_name,
        "has_style": has_style,
        "has_product_front": (base / "references" / "product_front.png").exists(),
        "mode": "client",
        "status": "selection_applied",
    })
    append_pipeline_log(base, "client_selection_applied", {
        "product_id": product_id,
        "product_name": product.get("name"),
        "scenario_id": scenario_id,
        "scenario_name": scenario.get("name"),
        "export_id": export_id,
        "prompt": prompt,
        "facade_mode": product.get("facade_mode"),
        "ies_files": saved_ies,
        "has_style": has_style,
        "has_product_front": (base / "references" / "product_front.png").exists(),
        "style_file": style_name,
    })
    return {"product": product, "scenario": scenario}


# Legacy aliases for older API paths
CLIENT_FIXTURES: list[dict] = []
CLIENT_TEMPLATES: list[dict] = []

app = FastAPI(title="NITEOS Concept Light Cloud")

# Разметка доработки и крупные data-URL в FormData иначе падают с "Part exceeded maximum size of 1024KB"
try:
    from starlette.formparsers import MultiPartParser

    MultiPartParser.max_part_size = 40 * 1024 * 1024
except Exception:
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name).strip()
    return cleaned or "file"


def project_dir(project_id: str) -> Path:
    path = PROJECTS_DIR / project_id
    if not path.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    return path


def ensure_project_dirs(base: Path) -> None:
    for name in ("input", "ies_library", "references", "output", "project_export"):
        (base / name).mkdir(parents=True, exist_ok=True)


def pipeline_log_path(base: Path) -> Path:
    return base / "pipeline_log.jsonl"


def append_pipeline_log(base: Path, step: str, data: dict | None = None) -> None:
    entry = {"ts": now_iso(), "step": step}
    if data:
        entry.update(data)
    path = pipeline_log_path(base)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def client_ip_from_request(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return ""


def log_ip_activity(
    *,
    action: str,
    request: Request | None = None,
    project_id: str = "",
    detail: dict | None = None,
) -> str:
    ip = client_ip_from_request(request)
    entry = {
        "ts": now_iso(),
        "ip": ip,
        "action": action,
        "project_id": project_id or "",
        "path": str(request.url.path) if request is not None else "",
        "method": request.method if request is not None else "",
        "user_agent": (request.headers.get("user-agent") or "")[:240] if request is not None else "",
        "detail": detail or {},
    }
    day_file = IP_ACTIVITY_DIR / f"{date.today().isoformat()}.jsonl"
    with day_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return ip


def track_project_action(
    base: Path,
    step: str,
    request: Request | None = None,
    data: dict | None = None,
) -> None:
    payload = dict(data or {})
    ip = log_ip_activity(
        action=step,
        request=request,
        project_id=base.name,
        detail={
            k: payload.get(k)
            for k in (
                "scenario_id",
                "filename",
                "status",
                "kind",
                "routerai_model",
                "files",
                "prompt_chars",
                "has_annotation",
                "error",
                "product_id",
            )
            if k in payload
        },
    )
    if ip:
        payload["client_ip"] = ip
    append_pipeline_log(base, step, payload)


def read_pipeline_log(base: Path) -> list[dict]:
    path = pipeline_log_path(base)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def mirror_to_library(src: Path, kind: Literal["source", "ies", "style"]) -> Path | None:
    if not src.exists() or not src.is_file():
        return None
    return copy_unique(src, library_root(kind), src.name)


def save_rgb(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=95)


def close_pending_feedback_for_new_render(base: Path) -> None:
    """Если прошлый рендер без оценки — зафиксировать как skipped и не терять историю."""
    meta = read_project_meta(base)
    history: list[dict] = list(meta.get("render_history") or [])
    changed = False
    for entry in history:
        if not isinstance(entry, dict):
            continue
        if entry.get("feedback_vote"):
            continue
        status = (entry.get("feedback_status") or "").strip().lower()
        if status in {"submitted", "skipped"}:
            continue
        entry["feedback_status"] = "skipped"
        entry["feedback_skipped_at"] = now_iso()
        changed = True
        archive_path = entry.get("generation_archive") or ""
        if archive_path:
            update_generation_archive(archive_path, {
                "feedback_status": "skipped",
                "feedback_skipped_at": entry["feedback_skipped_at"],
                "feedback_vote": "",
            })
    patch: dict = {"feedback_required": False}
    if changed:
        patch["render_history"] = history
    write_project_meta(base, patch)


def update_generation_archive(rel_or_name: str, patch: dict) -> None:
    """Обновить JSON-снимок генерации (оценка / skip)."""
    name = Path(str(rel_or_name or "")).name
    if not name:
        return
    path = GENERATIONS_DIR / name
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return
    data.update(patch or {})
    data["updated_at"] = now_iso()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def archive_generation_record(base: Path, entry: dict, *, client_ip: str = "") -> str:
    """Автосбор полной карточки генерации в cloud_data/generations/ — без ожидания оценки."""
    meta = read_project_meta(base)
    plan = meta.get("last_placement_plan") or {}
    auto_viz = meta.get("auto_viz") or {}
    hist_id = entry.get("id")
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = f"{stamp}_{base.name[:8]}_h{hist_id}_{uuid.uuid4().hex[:6]}.json"
    record = {
        "project_id": base.name,
        "history_id": hist_id,
        "kind": entry.get("kind") or "",
        "created_at": entry.get("created_at") or now_iso(),
        "feedback_status": entry.get("feedback_status") or "pending",
        "feedback_vote": entry.get("feedback_vote") or "",
        "feedback_comment": entry.get("feedback_comment") or "",
        "feedback_contact": entry.get("feedback_contact") or "",
        "feedback_issue_type": entry.get("feedback_issue_type") or "",
        "work_mode": entry.get("work_mode") or meta.get("work_mode") or "",
        "scenario_id": entry.get("scenario_id") or meta.get("render_scenario_id") or meta.get("dealer_scenario_id") or "",
        "scenario_name": entry.get("scenario_name") or meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or "",
        "product_id": entry.get("product_id") or meta.get("render_product_id") or meta.get("dealer_product_id") or "",
        "product_name": entry.get("product_name") or meta.get("render_product_name") or meta.get("dealer_product_name") or "",
        "auto_viz_ref": entry.get("auto_viz_ref") or meta.get("auto_viz_ref") or (auto_viz.get("filename") if isinstance(auto_viz, dict) else "") or "",
        "placement_family": entry.get("placement_family") or plan.get("family") or "",
        "placement_strategy": entry.get("placement_strategy") or plan.get("strategy") or plan.get("candidate_id") or "",
        "routerai_model": entry.get("routerai_model") or meta.get("routerai_model") or "",
        "facade_mode": entry.get("facade_mode") or read_facade_mode(base),
        "ies_names": entry.get("ies_names") or project_ies_names(base),
        "prompt": entry.get("prompt") or "",
        "prompt_chars": len(entry.get("prompt") or ""),
        "note": entry.get("note") or "",
        "history_file": entry.get("file") or "",
        "prompt_file": entry.get("prompt_file") or "",
        "source_file": "input/building.png" if (base / "input" / "building.png").exists() else "",
        "final_file": "output/final_imported_render.png" if (base / "output" / "final_imported_render.png").exists() else "",
        "style_file": "references/style_reference_target.png" if (base / "references" / "style_reference_target.png").exists() else "",
        "client_ip": client_ip or "",
        "render_audit": meta.get("last_render_audit") or {},
        "placement_plan": plan,
        "learning_guidance": meta.get("learning_guidance") or {},
        "urls": {
            "dealer": f"/dealer?project={base.name}",
            "source": f"/api/projects/{base.name}/file/input/building.png" if (base / "input" / "building.png").exists() else "",
            "final": f"/api/projects/{base.name}/file/output/{entry.get('file')}" if entry.get("file") else "",
            "prompt": f"/api/projects/{base.name}/file/output/{entry.get('prompt_file')}" if entry.get("prompt_file") else "",
        },
    }
    (GENERATIONS_DIR / fname).write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    append_pipeline_log(base, "generation_archived", {
        "history_id": hist_id,
        "archive": fname,
        "prompt_chars": record["prompt_chars"],
        "feedback_status": record["feedback_status"],
    })
    return fname


def save_render_history_entry(
    base: Path,
    *,
    kind: str,
    note: str = "",
    prompt: str = "",
    client_ip: str = "",
) -> dict | None:
    """Сохранить текущий финальный рендер в историю проекта (не перезаписывает final)."""
    final = base / "output" / "final_imported_render.png"
    if not final.exists():
        return None
    close_pending_feedback_for_new_render(base)
    history_dir = base / "output" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    meta = read_project_meta(base)
    history: list[dict] = list(meta.get("render_history") or [])
    seq = len(history) + 1
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_kind = re.sub(r"[^a-z0-9_]+", "_", kind.lower()).strip("_") or "render"
    fname = f"{seq:03d}_{stamp}_{safe_kind}.png"
    dest = history_dir / fname
    shutil.copy2(final, dest)
    prompt_text = (prompt or "").strip()
    if not prompt_text:
        prompt_path = base / "prompt.txt"
        if prompt_path.exists():
            prompt_text = prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
    prompt_file = ""
    if prompt_text:
        prompt_fname = f"{seq:03d}_{stamp}_{safe_kind}_prompt.txt"
        (history_dir / prompt_fname).write_text(prompt_text, encoding="utf-8")
        prompt_file = f"history/{prompt_fname}"
    plan = meta.get("last_placement_plan") or {}
    auto_viz = meta.get("auto_viz") or {}
    ies_names = project_ies_names(base)
    entry = {
        "id": seq,
        "file": f"history/{fname}",
        "prompt_file": prompt_file,
        "kind": kind,
        "note": (note or prompt_text[:500] or "")[:500],
        "prompt": prompt_text[:12000],
        "created_at": now_iso(),
        "work_mode": meta.get("work_mode") or "",
        "scenario_id": meta.get("render_scenario_id") or meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "",
        "scenario_name": meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or meta.get("client_scenario_name") or "",
        "product_id": meta.get("render_product_id") or meta.get("dealer_product_id") or meta.get("client_product_id") or "",
        "product_name": meta.get("render_product_name") or meta.get("dealer_product_name") or meta.get("client_product_name") or "",
        "auto_viz_ref": meta.get("auto_viz_ref") or (auto_viz.get("filename") if isinstance(auto_viz, dict) else "") or "",
        "placement_family": plan.get("family") or "",
        "placement_strategy": plan.get("strategy") or plan.get("candidate_id") or "",
        "routerai_model": meta.get("routerai_model") or "",
        "facade_mode": read_facade_mode(base),
        "ies_names": ies_names,
        "client_ip": (client_ip or "").strip(),
        "feedback_status": "pending",
        "feedback_vote": "",
        "feedback_comment": "",
        "feedback_contact": "",
        "feedback_issue_type": "",
        "feedback_at": "",
        "generation_archive": "",
    }
    archive_name = archive_generation_record(base, entry, client_ip=client_ip)
    entry["generation_archive"] = archive_name
    history.append(entry)
    write_project_meta(base, {"render_history": history})
    return entry


def attach_feedback_to_history_entry(
    base: Path,
    *,
    history_id,
    vote: str = "",
    comment: str = "",
    contact: str = "",
    issue_type: str = "",
) -> dict | None:
    """Дописать оценку/контакт/комментарий к конкретной записи истории рендера."""
    meta = read_project_meta(base)
    history: list[dict] = list(meta.get("render_history") or [])
    if not history:
        return None
    target = None
    if history_id is not None and str(history_id).strip() != "":
        for entry in history:
            if str(entry.get("id")) == str(history_id):
                target = entry
                break
    if target is None:
        target = history[-1]
    target["feedback_vote"] = (vote or "").strip()
    target["feedback_comment"] = (comment or "").strip()[:4000]
    target["feedback_contact"] = (contact or "").strip()[:200]
    target["feedback_issue_type"] = (issue_type or "").strip()
    target["feedback_at"] = now_iso()
    target["feedback_status"] = "submitted" if target["feedback_vote"] else "pending"
    if target.get("generation_archive"):
        update_generation_archive(target["generation_archive"], {
            "feedback_status": target["feedback_status"],
            "feedback_vote": target["feedback_vote"],
            "feedback_comment": target["feedback_comment"],
            "feedback_contact": target["feedback_contact"],
            "feedback_issue_type": target["feedback_issue_type"],
            "feedback_at": target["feedback_at"],
        })
    write_project_meta(base, {
        "render_history": history,
        "last_feedback_comment": target["feedback_comment"],
        "last_feedback_contact": target["feedback_contact"],
        "last_feedback_issue_type": target["feedback_issue_type"],
    })
    return target


def render_history_kind(base: Path) -> str:
    meta = read_project_meta(base)
    return "regenerate" if meta.get("render_history") else "render"


def write_project_meta(base: Path, data: dict) -> None:
    meta_path = base / "project.json"
    current = {}
    if meta_path.exists():
        current = json.loads(meta_path.read_text(encoding="utf-8"))
    current.update(data)
    current["updated_at"] = now_iso()
    meta_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def read_project_meta(base: Path) -> dict:
    meta_path = base / "project.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def project_relpath(base: Path, path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def first_existing_file(folder: Path, exts: set[str] | None = None) -> Path | None:
    if not folder.exists():
        return None
    for path in sorted(folder.rglob("*")):
        if path.is_file() and (exts is None or path.suffix.lower() in exts):
            return path
    return None


def quality_label_for_vote(vote: str | None) -> str:
    vote = (vote or "").strip().lower()
    if vote == "like":
        return "good"
    if vote == "dislike":
        return "bad"
    return "unrated"


def quality_label_for_rating(rating: int | None) -> str:
    """Legacy 1–5 scale; like/dislike maps to 5/1."""
    if rating is None or rating <= 0:
        return "unrated"
    if rating >= 4:
        return "good"
    if rating <= 2:
        return "bad"
    return "mixed"


def normalize_feedback_vote(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in {"like", "dislike"} else ""


def rating_from_vote(vote: str) -> int:
    if vote == "like":
        return 5
    if vote == "dislike":
        return 1
    return 0


FEEDBACK_ISSUE_LABELS = {
    "": "",
    "placement_incorrect": "incorrect fixture placement",
    "coverage_incomplete": "incomplete facade coverage",
    "overlit": "too much light or glare",
    "underlit": "not enough light",
    "style_mismatch": "lighting style mismatch",
    "other": "other issue",
}


def normalize_feedback_issue_type(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in FEEDBACK_ISSUE_LABELS else ""


def feedback_learning_note(payload: dict) -> str:
    issue = FEEDBACK_ISSUE_LABELS.get(payload.get("issue_type") or "", "")
    comment = (payload.get("comment") or "").strip()
    if issue and comment:
        return f"{issue}: {comment}"
    return issue or comment


def build_learning_snapshot(base: Path) -> dict:
    meta = read_project_meta(base)
    latest = base / "project_export" / "latest"
    prompt_path = base / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8", errors="ignore").strip() if prompt_path.exists() else ""
    final_path = base / "output" / "final_imported_render.png"
    last_history = meta.get("last_history_entry") or {}
    last_history_file = last_history.get("file") if isinstance(last_history, dict) else ""
    annotation_path = base / "output" / "edit_annotation.png"
    return {
        "project_id": base.name,
        "status": meta.get("status") or "",
        "facade_mode": read_facade_mode(base),
        "scenario": {
            "id": meta.get("render_scenario_id") or meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "",
            "name": meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or meta.get("client_scenario_name") or "",
        },
        "product": {
            "id": meta.get("render_product_id") or meta.get("dealer_product_id") or meta.get("client_product_id") or "",
            "name": meta.get("render_product_name") or meta.get("dealer_product_name") or meta.get("client_product_name") or "",
        },
        "ies_names": project_ies_names(base),
        "routerai_model": meta.get("routerai_model") or "",
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "artifacts": {
            "source": project_relpath(base, first_existing_file(base / "input", {".png", ".jpg", ".jpeg", ".webp"})),
            "style_reference": project_relpath(base, first_existing_file(base / "references", {".png", ".jpg", ".jpeg", ".webp"})),
            "light_plan": project_relpath(base, latest / "02_light_plan_reference.png" if (latest / "02_light_plan_reference.png").exists() else None),
            "final_render": project_relpath(base, final_path if final_path.exists() else None),
            "last_history_render": last_history_file,
            "edit_annotation": project_relpath(base, annotation_path if annotation_path.exists() else None),
        },
        "render_history_count": len(meta.get("render_history") or []),
        "placement_plan": meta.get("last_placement_plan") or {},
        "placement_candidates": meta.get("last_placement_candidates") or [],
        "render_audit": meta.get("last_render_audit") or {},
        "updated_at": meta.get("updated_at") or "",
    }


def append_learning_event(
    base: Path,
    event_type: str,
    *,
    payload: dict | None = None,
    rating: int | None = None,
    vote: str | None = None,
) -> dict:
    safe_vote = normalize_feedback_vote(vote or "")
    if safe_vote and (rating is None or rating <= 0):
        rating = rating_from_vote(safe_vote)
    quality = quality_label_for_vote(safe_vote) if safe_vote else quality_label_for_rating(rating)
    entry = {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "created_at": now_iso(),
        "quality_label": quality,
        "snapshot": build_learning_snapshot(base),
        "payload": payload or {},
    }
    if safe_vote:
        entry["vote"] = safe_vote
    if rating is not None:
        entry["rating"] = max(0, min(5, int(rating or 0)))
    line = json.dumps(entry, ensure_ascii=False)
    LEARNING_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEARNING_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    with (base / "learning_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return entry


def learning_events_summary(limit: int = 20) -> dict:
    if not LEARNING_EVENTS_PATH.exists():
        return {"total": 0, "by_type": {}, "by_quality": {}, "recent": []}
    by_type: dict[str, int] = {}
    by_quality: dict[str, int] = {}
    recent: list[dict] = []
    total = 0
    for line in LEARNING_EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        event_type = str(event.get("event_type") or "unknown")
        quality = str(event.get("quality_label") or "unknown")
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_quality[quality] = by_quality.get(quality, 0) + 1
        snapshot = event.get("snapshot") or {}
        scenario = snapshot.get("scenario") or {}
        product = snapshot.get("product") or {}
        recent.append({
            "event_id": event.get("event_id") or "",
            "event_type": event_type,
            "created_at": event.get("created_at") or "",
            "project_id": snapshot.get("project_id") or "",
            "quality_label": quality,
            "rating": event.get("rating", None),
            "scenario_id": scenario.get("id") or "",
            "scenario_name": scenario.get("name") or "",
            "product_id": product.get("id") or "",
            "product_name": product.get("name") or "",
            "prompt_chars": snapshot.get("prompt_chars") or 0,
        })
    return {
        "total": total,
        "by_type": by_type,
        "by_quality": by_quality,
        "recent": recent[-max(1, min(limit, 100)):][::-1],
    }


def learned_rules_summary(max_events: int = 1000) -> dict:
    groups: dict[str, dict] = {}
    for event in iter_learning_events(max_events):
        snapshot = event.get("snapshot") or {}
        plan = snapshot.get("placement_plan") or {}
        family = plan.get("family") or "unknown"
        strategy = plan.get("strategy") or plan.get("candidate_id") or "unknown"
        key = f"{family}::{strategy}"
        group = groups.setdefault(key, {
            "family": family,
            "strategy": strategy,
            "samples": 0,
            "good": 0,
            "mixed": 0,
            "bad": 0,
            "edited": 0,
            "avg_rating": 0.0,
            "rating_sum": 0,
            "rating_count": 0,
            "repeat": [],
            "avoid": [],
            "fix_before_render": [],
        })
        group["samples"] += 1
        quality = event.get("quality_label") or "unrated"
        if quality in ("good", "mixed", "bad"):
            group[quality] += 1
        if event.get("event_type") == "render_edited":
            group["edited"] += 1
        if isinstance(event.get("rating"), int) and event["rating"] > 0:
            group["rating_sum"] += event["rating"]
            group["rating_count"] += 1

        payload = event.get("payload") or {}
        if quality == "good":
            append_unique_note(group["repeat"], payload.get("comment") or payload.get("ies_summary") or "", limit=5)
        if quality == "bad":
            append_unique_note(group["avoid"], payload.get("comment") or "", limit=5)
        if event.get("event_type") == "render_edited":
            append_unique_note(group["fix_before_render"], payload.get("instruction") or payload.get("comment") or "", limit=5)

    rules = []
    for group in groups.values():
        if group["rating_count"]:
            group["avg_rating"] = round(group["rating_sum"] / group["rating_count"], 2)
        del group["rating_sum"]
        del group["rating_count"]
        if group["bad"] > group["good"] or group["edited"] >= max(2, group["good"]):
            group["recommendation"] = "use_with_caution"
        elif group["good"] >= max(1, group["bad"] + group["edited"]):
            group["recommendation"] = "prefer_when_matching"
        else:
            group["recommendation"] = "neutral"
        rules.append(group)
    rules.sort(key=lambda item: (item["samples"], item["good"] - item["bad"] - item["edited"]), reverse=True)
    return {"total_groups": len(rules), "rules": rules}


def iter_learning_events(max_events: int = 500) -> list[dict]:
    if not LEARNING_EVENTS_PATH.exists():
        return []
    lines = [
        line.strip()
        for line in LEARNING_EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]
    events: list[dict] = []
    for line in lines[-max(1, max_events):]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", " ", (value or "").lower(), flags=re.IGNORECASE).strip()


def learning_similarity_score(current: dict, event: dict) -> int:
    snapshot = event.get("snapshot") or {}
    if snapshot.get("project_id") == current.get("project_id"):
        return 0

    score = 0
    current_scenario = current.get("scenario") or {}
    event_scenario = snapshot.get("scenario") or {}
    current_product = current.get("product") or {}
    event_product = snapshot.get("product") or {}

    if current_scenario.get("id") and current_scenario.get("id") == event_scenario.get("id"):
        score += 6
    elif current_scenario.get("name") and normalize_token(current_scenario.get("name")) == normalize_token(event_scenario.get("name")):
        score += 3

    if current_product.get("id") and current_product.get("id") == event_product.get("id"):
        score += 4
    elif current_product.get("name") and normalize_token(current_product.get("name")) == normalize_token(event_product.get("name")):
        score += 2

    current_ies = {normalize_token(name) for name in current.get("ies_names") or []}
    event_ies = {normalize_token(name) for name in snapshot.get("ies_names") or []}
    score += min(4, len(current_ies & event_ies) * 2)

    if current.get("facade_mode") and current.get("facade_mode") == snapshot.get("facade_mode"):
        score += 1

    current_facade = current.get("placement_plan", {}).get("facade") or {}
    event_facade = snapshot.get("placement_plan", {}).get("facade") or {}
    current_tags = set(current_facade.get("tags") or [])
    event_tags = set(event_facade.get("tags") or [])
    score += min(4, len(current_tags & event_tags))
    if current_facade.get("composition") and current_facade.get("composition") == event_facade.get("composition"):
        score += 1
    if current_facade.get("texture_complexity") and current_facade.get("texture_complexity") == event_facade.get("texture_complexity"):
        score += 1

    quality = event.get("quality_label") or ""
    if quality in {"good", "bad"}:
        score += 1
    if event.get("event_type") == "render_edited":
        score += 1
    return score


def event_learning_lesson(event: dict) -> str:
    snapshot = event.get("snapshot") or {}
    payload = event.get("payload") or {}
    quality = event.get("quality_label") or "unrated"
    scenario = snapshot.get("scenario") or {}
    product = snapshot.get("product") or {}
    label = ", ".join(
        part for part in (
            scenario.get("name") or scenario.get("id") or "",
            product.get("name") or product.get("id") or "",
        )
        if part
    )
    prefix = f"Similar case {snapshot.get('project_id') or ''}".strip()
    if label:
        prefix += f" ({label})"

    if event.get("event_type") == "render_edited":
        instruction = (payload.get("instruction") or "").strip()
        if instruction:
            return f"{prefix}: previous render needed correction: {instruction[:220]}. Avoid repeating that mistake."

    if quality == "good":
        note = (payload.get("comment") or payload.get("ies_summary") or "").strip()
        if note:
            return f"{prefix}: high-rated result. Preserve the successful placement logic: {note[:220]}."
        return f"{prefix}: high-rated result. Prefer the same consistent facade-wide placement rhythm and avoid missing dark facade zones."

    if quality == "bad":
        note = (payload.get("comment") or "").strip()
        if note:
            return f"{prefix}: low-rated result. Treat as a warning: {note[:220]}."
        return f"{prefix}: low-rated result. Do not leave partial or inconsistent fixture placement; cover the full intended facade rhythm."

    return ""


def append_unique_note(items: list[str], note: str, limit: int = 3) -> None:
    cleaned = re.sub(r"\s+", " ", (note or "").strip())
    if not cleaned:
        return
    cleaned = cleaned[:240]
    key = normalize_token(cleaned)
    if not key:
        return
    existing = {normalize_token(item) for item in items}
    if key not in existing and len(items) < limit:
        items.append(cleaned)


def placement_strategy_memory(family: str = "", strategy: str = "", max_events: int = 500) -> dict:
    stats = {
        "family": family,
        "strategy": strategy,
        "samples": 0,
        "good": 0,
        "mixed": 0,
        "bad": 0,
        "edited": 0,
        "audit_needs_review": 0,
        "audit_low_signal": 0,
        "avg_rating": 0.0,
        "score_adjustment": 0,
        "risk_adjustment": 0,
        "success_notes": [],
        "warning_notes": [],
        "edit_notes": [],
    }
    rating_sum = 0
    rating_count = 0
    for event in iter_learning_events(max_events):
        snapshot = event.get("snapshot") or {}
        plan = snapshot.get("placement_plan") or {}
        if family and plan.get("family") != family:
            continue
        if strategy and (plan.get("strategy") or plan.get("candidate_id")) != strategy:
            continue
        stats["samples"] += 1
        quality = event.get("quality_label") or "unrated"
        if quality in ("good", "mixed", "bad"):
            stats[quality] += 1
        if event.get("event_type") == "render_edited":
            stats["edited"] += 1
        payload = event.get("payload") or {}
        render_audit = payload.get("render_audit") or snapshot.get("render_audit") or {}
        audit_status = render_audit.get("status") or ""
        if audit_status == "needs_review":
            stats["audit_needs_review"] += 1
            append_unique_note(stats["warning_notes"], "automatic image audit found possible facade coverage gaps")
        elif audit_status == "low_signal":
            stats["audit_low_signal"] += 1
        if quality == "good":
            append_unique_note(stats["success_notes"], payload.get("comment") or payload.get("ies_summary") or "")
        if quality == "bad":
            append_unique_note(stats["warning_notes"], feedback_learning_note(payload))
        if event.get("event_type") == "render_edited":
            append_unique_note(stats["edit_notes"], payload.get("instruction") or payload.get("comment") or "")
        if isinstance(event.get("rating"), int) and event["rating"] > 0:
            rating_sum += event["rating"]
            rating_count += 1

    if rating_count:
        stats["avg_rating"] = round(rating_sum / rating_count, 2)
    stats["score_adjustment"] = stats["good"] * 6 + stats["mixed"] * 1 - stats["bad"] * 8 - stats["edited"] * 3 - stats["audit_needs_review"] * 4
    stats["risk_adjustment"] = stats["bad"] * 6 + stats["edited"] * 4 + stats["audit_needs_review"] * 5 - stats["good"] * 3
    return stats


def build_learning_guidance(base: Path, prompt: str, limit: int = 4, placement_plan: dict | None = None) -> tuple[str, dict]:
    meta = read_project_meta(base)
    # Auto facade mode must not lean on old project memory / old generated cases.
    if (meta.get("work_mode") or "").strip().lower() == "auto":
        return prompt, {"applied": False, "matches": 0, "lessons": [], "skipped": "auto_mode"}
    current = build_learning_snapshot(base)
    if placement_plan:
        current["placement_plan"] = placement_plan
    family = str((placement_plan or {}).get("family") or "")
    candidates: list[tuple[int, dict]] = []
    for event in iter_learning_events():
        score = learning_similarity_score(current, event)
        if score <= 0:
            continue
        lesson = event_learning_lesson(event)
        if not lesson:
            continue
        lesson_l = lesson.lower()
        # Keep facade jobs free from old ground-pole lessons.
        if family and family != "ground_poles" and ("pole" in lesson_l or "фонар" in lesson_l or "street" in lesson_l):
            continue
        candidates.append((score, event))

    candidates.sort(key=lambda item: (item[0], item[1].get("created_at") or ""), reverse=True)
    selected = candidates[:max(0, limit)]
    lessons = [event_learning_lesson(event) for _, event in selected]
    lessons = [lesson for lesson in lessons if lesson]
    if not lessons:
        return prompt, {"applied": False, "matches": 0, "lessons": []}

    block = (
        "\n\nLEARNING MEMORY FROM PREVIOUS PROJECTS:\n"
        "Use these as placement guidance only. Do not copy facade geometry, text, logos, or unrelated styling.\n"
        + "\n".join(f"- {lesson}" for lesson in lessons)
        + "\n"
    )
    return prompt.rstrip() + block, {
        "applied": True,
        "matches": len(selected),
        "lessons": lessons,
        "event_ids": [event.get("event_id") or "" for _, event in selected],
        "scores": [score for score, _ in selected],
    }


def analyze_facade_source(base: Path) -> dict:
    source = base / "input" / "building.png"
    info = {
        "source": project_relpath(base, source if source.exists() else None),
        "width": 0,
        "height": 0,
        "aspect": 0.0,
        "composition": "unknown",
        "estimated_scale": "unknown",
        "avg_brightness": 0,
        "contrast": 0,
        "edge_density": 0.0,
        "brightness_class": "unknown",
        "texture_complexity": "unknown",
        "tags": [],
    }
    if not source.exists():
        return info
    try:
        with Image.open(source) as img:
            width, height = img.size
            sample = img.convert("L").resize((96, 64))
            pixels = list(sample.getdata())
    except Exception:
        return info

    aspect = round(width / max(1, height), 3)
    if aspect >= 1.65:
        composition = "wide_facade"
    elif aspect <= 0.85:
        composition = "tall_facade"
    else:
        composition = "balanced_facade"

    max_side = max(width, height)
    if max_side >= 2400:
        estimated_scale = "high_detail"
    elif max_side >= 1200:
        estimated_scale = "medium_detail"
    else:
        estimated_scale = "low_detail"

    avg_brightness = int(sum(pixels) / max(1, len(pixels)))
    variance = sum((p - avg_brightness) ** 2 for p in pixels) / max(1, len(pixels))
    contrast = int(variance ** 0.5)
    edge_hits = 0
    comparisons = 0
    sample_w, sample_h = sample.size
    for y in range(sample_h - 1):
        row = y * sample_w
        next_row = (y + 1) * sample_w
        for x in range(sample_w - 1):
            p = pixels[row + x]
            if abs(p - pixels[row + x + 1]) > 24:
                edge_hits += 1
            if abs(p - pixels[next_row + x]) > 24:
                edge_hits += 1
            comparisons += 2
    edge_density = round(edge_hits / max(1, comparisons), 3)

    if avg_brightness < 75:
        brightness_class = "dark_source"
    elif avg_brightness > 175:
        brightness_class = "bright_source"
    else:
        brightness_class = "balanced_source"

    if edge_density >= 0.22 or contrast >= 62:
        texture_complexity = "high_detail_facade"
    elif edge_density >= 0.11 or contrast >= 38:
        texture_complexity = "medium_detail_facade"
    else:
        texture_complexity = "low_detail_facade"

    tags = [composition, estimated_scale, brightness_class, texture_complexity]

    info.update({
        "width": width,
        "height": height,
        "aspect": aspect,
        "composition": composition,
        "estimated_scale": estimated_scale,
        "avg_brightness": avg_brightness,
        "contrast": contrast,
        "edge_density": edge_density,
        "brightness_class": brightness_class,
        "texture_complexity": texture_complexity,
        "tags": tags,
    })
    return info


def audit_render_coverage(base: Path, final_path: Path, placement_plan: dict | None = None) -> dict:
    """Estimate whether generated lighting reaches comparable facade zones.

    This is an image diagnostic, not a photometric calculation. It flags likely
    omissions for the agent's memory and a human review without another render.
    """
    facade = (placement_plan or {}).get("facade") or analyze_facade_source(base)
    strategy = (placement_plan or {}).get("strategy") or (placement_plan or {}).get("candidate_id") or ""
    family = (placement_plan or {}).get("family") or ""
    result = {
        "version": 1,
        "audited_at": now_iso(),
        "strategy": strategy,
        "family": family,
        "composition": facade.get("composition") or "unknown",
        "status": "unavailable",
        "coverage_score": 0,
        "signal_level": 0,
        "dark_zones": [],
        "zones": [],
        "recommendation": "",
    }
    if not final_path.exists():
        return result
    try:
        with Image.open(final_path) as image:
            sample = image.convert("L").resize((96, 64))
            width, height = sample.size
            pixels = list(sample.getdata())
    except Exception:
        return result

    x0, x1 = int(width * 0.08), int(width * 0.92)
    y0, y1 = int(height * 0.12), int(height * 0.92)
    composition = result["composition"]
    cols, rows = (3, 2) if composition == "wide_facade" else ((2, 3) if composition == "tall_facade" else (3, 3))
    crop_values = [pixels[y * width + x] for y in range(y0, y1) for x in range(x0, x1)]
    if not crop_values:
        return result
    average = sum(crop_values) / len(crop_values)
    variance = sum((value - average) ** 2 for value in crop_values) / len(crop_values)
    contrast = variance ** 0.5
    signal_threshold = min(230, average + max(12, contrast * 0.35))
    zone_means: list[float] = []
    zones: list[dict] = []
    for row in range(rows):
        for col in range(cols):
            left = x0 + (x1 - x0) * col // cols
            right = x0 + (x1 - x0) * (col + 1) // cols
            top = y0 + (y1 - y0) * row // rows
            bottom = y0 + (y1 - y0) * (row + 1) // rows
            values = [pixels[y * width + x] for y in range(top, bottom) for x in range(left, right)]
            zone_mean = sum(values) / max(1, len(values))
            bright_ratio = sum(value >= signal_threshold for value in values) / max(1, len(values))
            zone_means.append(zone_mean)
            zones.append({
                "id": f"r{row + 1}c{col + 1}",
                "mean_luminance": round(zone_mean, 1),
                "bright_ratio": round(bright_ratio, 3),
            })

    median_mean = sorted(zone_means)[len(zone_means) // 2]
    signal_level = sum(zone_means) / max(1, len(zone_means))
    signal_floor = max(8.0, median_mean * 0.48)
    active_zones = 0
    dark_zones: list[str] = []
    for zone in zones:
        active = zone["mean_luminance"] >= signal_floor or zone["bright_ratio"] >= 0.025
        zone["active"] = active
        if active:
            active_zones += 1
        else:
            dark_zones.append(zone["id"])

    coverage_score = round(active_zones * 100 / max(1, len(zones)))
    result.update({
        "coverage_score": coverage_score,
        "signal_level": round(signal_level, 1),
        "dark_zones": dark_zones,
        "zones": zones,
    })
    strict_coverage = strategy == "full_coverage" or family in {"horizontal_lines", "vertical_projectors", "wash"}
    if signal_level < 16:
        result.update({"status": "low_signal", "recommendation": "The generated scene is too dark for a reliable coverage check."})
    elif strict_coverage and coverage_score < 67:
        result.update({"status": "needs_review", "recommendation": "Possible facade coverage gaps detected. Review the listed zones before reusing this placement strategy."})
    elif strict_coverage and dark_zones:
        result.update({"status": "watch", "recommendation": "Most facade zones contain light, but darker zones should be checked against the selected scenario."})
    else:
        result.update({"status": "ok", "recommendation": "No obvious coverage gap was detected by the image audit."})
    return result


def scenario_family_for_plan(scenario_id: str, scenario_category: str, prompt: str) -> str:
    text = normalize_token(" ".join([scenario_id, scenario_category, prompt]))
    if "park" in text or "ground" in text or "ntpark" in text:
        return "ground_poles"
    if "wash" in text or "graze" in text or "залив" in text:
        return "wash"
    if "vertical" in text or "columns" in text or "projector" in text or "xray" in text:
        return "vertical_projectors"
    if "horizontal" in text:
        return "horizontal_lines"
    if "cornice" in text or "top_bottom" in text or "contour" in text:
        return "cornice_contour"
    if "mix" in text or "combined" in text:
        return "combined_layers"
    return "general_architectural"


def placement_plan_rules(family: str, facade: dict) -> list[str]:
    composition = facade.get("composition") or "unknown"
    base_rules = [
        "Cover the whole visible building according to the selected lighting logic; do not stop the pattern on only one side or one floor unless the scenario explicitly says so.",
        "Follow real architectural lines: cornices, floor bands, pilasters, columns, window rhythm, entrances, corners, canopies, and facade plane breaks.",
        "Keep fixtures and beams off window glass unless the scenario is about glass/entrance emphasis; do not invent extra products outside selected IES/product intent.",
    ]
    if composition == "wide_facade":
        base_rules.append("Because the facade is wide, repeat the lighting rhythm across all visible bays and include both left and right edge/corner zones.")
    elif composition == "tall_facade":
        base_rules.append("Because the facade is tall, maintain vertical continuity from base to upper architectural boundary without leaving middle floors unlit.")
    else:
        base_rules.append("Balance coverage horizontally and vertically so the central and side facade zones read as one designed scheme.")

    family_rules = {
        "horizontal_lines": [
            "Primary placement: continuous horizontal linear runs along floor bands or between window rows across the full visible facade width.",
            "Keep line height consistent from bay to bay; do not add vertical accents, poles, or random projectors.",
            "If a band is interrupted by an entrance or corner, resume the same line on the next architecturally aligned segment.",
        ],
        "vertical_projectors": [
            "Primary placement: repeated vertical uplight/downlight accents in pilasters, columns, or wall bays between openings.",
            "Use an even architectural rhythm: one accent per comparable bay/column group, including side zones when visible.",
            "Do not place beams across windows; aim along solid wall, column, stone, brick, or panel surfaces.",
        ],
        "cornice_contour": [
            "Primary placement: continuous contour along roofline/cornice or selected top/bottom architectural edge.",
            "Keep the contour as a clean uninterrupted line where architecture allows; avoid adding unrelated vertical/wash layers.",
            "If lower/base light is requested, keep it as a separate lower line aligned with plinth or first-floor band.",
        ],
        "wash": [
            "Primary placement: broad even wash/graze across facade planes, with soft overlap between adjacent zones.",
            "Avoid spotty isolated beams; coverage should read as a continuous illuminated surface.",
            "Preserve facade texture and relief with moderate contrast, no overexposed flat glow.",
        ],
        "ground_poles": [
            "Primary placement: pole or bollard fixtures belong on the ground/sidewalk/road edge in front of the facade, not mounted on the wall.",
            "Keep pole spacing regular along the facade; concentrate additional poles only near main entrance/glass zones if requested.",
            "Light should create ground pools and soft lower-facade illumination while preserving the building architecture.",
        ],
        "combined_layers": [
            "Use a clear hierarchy: one primary layer, one secondary accent layer, and optional entrance/base emphasis.",
            "Do not let layers conflict; horizontal lines, vertical accents, and wash must align to the same facade rhythm.",
            "Coverage must remain complete: if a layer starts on one repeated bay type, continue it through all comparable visible bays.",
        ],
        "general_architectural": [
            "Choose the dominant architectural rhythm first, then place fixtures consistently on all matching elements.",
            "Prefer fewer coherent repeated elements over many random isolated lights.",
            "Entrance, roofline, corners, and repeated bays should be resolved as a single scheme.",
        ],
    }
    return base_rules + family_rules.get(family, family_rules["general_architectural"])


def candidate_strategy_rules(family: str, strategy: str, facade: dict) -> list[str]:
    composition = facade.get("composition") or "unknown"
    if strategy == "full_coverage":
        rules = [
            "Strategy: full coverage. Continue the selected lighting rhythm across every comparable visible bay/zone.",
            "Resolve left edge, center, right edge, roofline/top boundary, base/lower boundary, and entrance/canopy zones as part of one complete scheme.",
            "If vertical accents are used, continue them through EVERY visible floor band on that bay — lower, middle and upper — with no dark skipped floors.",
            "Do not place street lamp posts or road/sidewalk poles unless the selected family is explicitly ground_poles.",
        ]
        if composition == "wide_facade":
            rules.append("For a wide facade, split placement mentally into left/center/right thirds and verify the same scenario logic is present in all thirds.")
        if composition == "tall_facade":
            rules.append("For a tall facade, split placement mentally into lower/middle/upper zones and verify continuity through all height zones.")
        return rules

    if strategy == "accent_focus":
        return [
            "Strategy: accent focus. Emphasize the main entrance, strongest facade rhythm, and most important architectural axes first.",
            "Keep accents repeated on comparable architectural elements so the result does not look like isolated random spots.",
            "Do not over-light secondary surfaces; preserve hierarchy while still avoiding accidental dark gaps in the intended lit zones.",
        ]

    if strategy == "conservative_clean":
        return [
            "Strategy: conservative clean. Use fewer lighting elements, but make every element continuous, aligned, and architecturally justified.",
            "Prefer a clean readable scheme over decorative clutter; remove any fixture idea that is not supported by selected product/IES.",
            "If uncertain, keep to the core scenario family and avoid adding unrelated layers.",
        ]

    return []


def score_placement_candidate(candidate: dict, memory: dict | None = None) -> dict:
    family = candidate.get("family") or ""
    strategy = candidate.get("strategy") or ""
    facade = candidate.get("facade") or {}
    rules = candidate.get("rules") or []
    composition = facade.get("composition") or "unknown"

    coverage = 50
    consistency = 35
    risk = 25
    signals: list[str] = []

    def adjust(label: str, coverage_delta: int = 0, consistency_delta: int = 0, risk_delta: int = 0) -> None:
        nonlocal coverage, consistency, risk
        coverage += coverage_delta
        consistency += consistency_delta
        risk += risk_delta
        signals.append(label)

    if strategy == "full_coverage":
        adjust("full facade coverage", 30, 12, -12)
    elif strategy == "accent_focus":
        adjust("focused accents", 12, 8, 2)
    elif strategy == "conservative_clean":
        adjust("clean limited scheme", 8, 16, -4)

    if composition == "wide_facade" and strategy != "full_coverage":
        adjust("wide facade needs continuity", -6, 0, 8)
    if composition == "tall_facade" and strategy == "accent_focus":
        adjust("tall facade can lose middle floors", 0, 0, 6)

    if family in {"combined_layers", "general_architectural"} and strategy == "conservative_clean":
        adjust("complex family benefits from restraint", 0, 4, -4)
    if family in {"horizontal_lines", "vertical_projectors", "wash"} and strategy == "full_coverage":
        adjust("scenario requires repeated facade rhythm", 8, 0, -4)
    if family == "cornice_contour":
        if strategy == "conservative_clean":
            adjust("contour scenario favors a restrained continuous line", 12, 10, -9)
        elif strategy == "full_coverage":
            adjust("contour scenario should not over-light facade planes", 0, 0, 9)
    if family == "ground_poles":
        if strategy == "conservative_clean":
            adjust("ground lighting needs controlled spacing", 10, 8, -8)
        elif strategy == "full_coverage":
            adjust("ground lighting must avoid a dense wall of fixtures", -8, 0, 13)

    photometry = [item for item in candidate.get("ies_photometry") or [] if item.get("parsed")]
    beam_classes = {item.get("beam_class") for item in photometry}
    forms = {item.get("optical_form") for item in photometry}
    if "linear" in forms:
        if family in {"horizontal_lines", "cornice_contour"} and strategy == "conservative_clean":
            adjust("linear optic matches continuous architectural bands", 8, 8, -6)
        elif strategy == "accent_focus":
            adjust("linear optic is weak for isolated point accents", 0, -3, 6)
    if "compact" in forms and "linear" not in forms:
        if family in {"vertical_projectors", "ground_poles"} and strategy == "accent_focus":
            adjust("compact optic supports discrete mounted accents", 8, 6, -4)
        elif family == "horizontal_lines" and strategy == "full_coverage":
            adjust("compact optic risks a broken linear rhythm", -5, -3, 7)
    if "narrow" in beam_classes:
        if strategy == "full_coverage":
            adjust("narrow beams need overlap across repeated bays", 4, 0, 4)
        elif strategy == "accent_focus":
            adjust("narrow beams support precise accents", 5, 4, -2)
    if "wide" in beam_classes:
        if strategy == "full_coverage":
            adjust("wide beams support an even wash", 6, 3, -4)
        elif strategy == "accent_focus":
            adjust("wide beams can spill outside accent zones", 0, -2, 5)

    if len(rules) >= 8:
        consistency += 3
    memory = memory or {}
    memory_score = int(memory.get("score_adjustment") or 0)
    memory_risk = int(memory.get("risk_adjustment") or 0)
    adjusted_risk = max(0, risk + memory_risk)
    final_score = max(0, coverage) + max(0, consistency) - adjusted_risk + memory_score
    return {
        "coverage": max(0, min(100, coverage)),
        "consistency": max(0, min(100, consistency)),
        "risk": max(0, min(100, adjusted_risk)),
        "base_risk": max(0, min(100, risk)),
        "memory_score_adjustment": memory_score,
        "memory_risk_adjustment": memory_risk,
        "memory_samples": int(memory.get("samples") or 0),
        "signals": signals,
        "final": final_score,
    }


def build_placement_candidates(base: Path, prompt: str) -> list[dict]:
    base_plan = build_placement_plan(base, prompt)
    candidates: list[dict] = []
    for strategy in ("full_coverage", "accent_focus", "conservative_clean"):
        candidate = json.loads(json.dumps(base_plan, ensure_ascii=False))
        candidate["candidate_id"] = strategy
        candidate["strategy"] = strategy
        candidate["rules"] = (
            placement_plan_rules(candidate["family"], candidate["facade"])
            + photometric_placement_rules(candidate.get("ies_photometry") or [])
            + candidate_strategy_rules(candidate["family"], strategy, candidate["facade"])
        )
        memory = placement_strategy_memory(candidate["family"], strategy)
        candidate["strategy_memory"] = memory
        candidate["score"] = score_placement_candidate(candidate, memory)
        candidates.append(candidate)
    candidates.sort(key=lambda item: item.get("score", {}).get("final", 0), reverse=True)
    return candidates


def build_placement_plan(base: Path, prompt: str) -> dict:
    meta = read_project_meta(base)
    scenario_id = meta.get("render_scenario_id") or meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or ""
    scenario_name = meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or meta.get("client_scenario_name") or ""
    scenario_category = ""
    if scenario_id:
        try:
            scenario_category = client_scenario_by_id(scenario_id).get("category", "")
        except HTTPException:
            scenario_category = ""
    product_id = meta.get("render_product_id") or meta.get("dealer_product_id") or meta.get("client_product_id") or ""
    product_name = meta.get("render_product_name") or meta.get("dealer_product_name") or meta.get("client_product_name") or ""
    ies_names = project_ies_names(base)
    ies_photometry = project_ies_photometry(base)
    facade = analyze_facade_source(base)
    family = scenario_family_for_plan(scenario_id, scenario_category, prompt)
    rules = placement_plan_rules(family, facade) + photometric_placement_rules(ies_photometry)
    return {
        "created_at": now_iso(),
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "scenario_category": scenario_category,
        "product_id": product_id,
        "product_name": product_name,
        "ies_names": ies_names,
        "ies_photometry": ies_photometry,
        "facade": facade,
        "family": family,
        "rules": rules,
        "coverage_checklist": [
            "All visible repeated facade zones covered according to scenario.",
            "No major dark gaps where the same lighting rhythm should continue.",
            "No extra fixture type outside selected product/IES logic.",
            "No red markup, labels, UI text, logos, or watermarks in final render.",
        ],
    }


def append_placement_plan_to_prompt(prompt: str, plan: dict) -> str:
    rules = plan.get("rules") or []
    checklist = plan.get("coverage_checklist") or []
    facade = plan.get("facade") or {}
    memory = plan.get("strategy_memory") or {}
    family = plan.get("family") or ""
    block = [
        "",
        "AGENT LIGHTING PLACEMENT PLAN:",
        f"- Scenario family: {family or 'unknown'}",
        f"- Selected strategy: {plan.get('strategy') or plan.get('candidate_id') or 'single_plan'}",
        f"- Strategy score: {json.dumps(plan.get('score') or {}, ensure_ascii=False)}",
        f"- Strategy memory: {json.dumps(plan.get('strategy_memory') or {}, ensure_ascii=False)}",
        f"- Facade geometry: {facade.get('composition') or 'unknown'}, aspect {facade.get('aspect') or 0}, source {facade.get('width') or 0}x{facade.get('height') or 0}",
        f"- Facade tags: {', '.join(facade.get('tags') or []) or 'unknown'}; brightness {facade.get('avg_brightness') or 0}; contrast {facade.get('contrast') or 0}; edge density {facade.get('edge_density') or 0}",
    ]
    if plan.get("product_name") or plan.get("product_id"):
        block.append(f"- Selected product: {plan.get('product_name') or plan.get('product_id')}")
    if plan.get("ies_names"):
        block.append("- Selected IES files: " + "; ".join(plan.get("ies_names") or []))
    for item in plan.get("ies_photometry") or []:
        if item.get("parsed"):
            block.append(
                "- IES photometry: "
                f"{item.get('filename')}; {item.get('optical_form')} optic; "
                f"{item.get('beam_class')} beam {item.get('beam_angle_deg')} deg; "
                f"nominal {item.get('nominal_lumens')} lm; peak {item.get('peak_candela')} cd"
            )
    if family != "ground_poles":
        block.append("- Hard constraints for facade schemes:")
        block.append("  1. No streetlights, globe lamps, road poles or sidewalk park fixtures.")
        block.append("  2. Vertical accents must continue full visible height of each bay; no dark mid-floor bands.")
        block.append("  3. Cover left wing, center/corner mass and right wing with one coherent scheme.")
    block.append("- Placement rules:")
    block.extend(f"  {idx}. {rule}" for idx, rule in enumerate(rules, 1))
    if memory.get("success_notes") or memory.get("warning_notes") or memory.get("edit_notes"):
        block.append("- Learned strategy notes:")
        for note in memory.get("success_notes") or []:
            block.append(f"  repeat: {note}")
        for note in memory.get("warning_notes") or []:
            block.append(f"  avoid: {note}")
        for note in memory.get("edit_notes") or []:
            block.append(f"  fix-before-render: {note}")
    block.append("- Final self-check before rendering:")
    block.extend(f"  {idx}. {item}" for idx, item in enumerate(checklist, 1))
    block.append("Apply this plan as binding placement logic while preserving the source building geometry and materials.")
    return prompt.rstrip() + "\n".join(block) + "\n"


def project_summary(base: Path) -> dict:
    meta = read_project_meta(base) | {"id": base.name}
    input_dir = base / "input"
    ies_dir = base / "ies_library"
    ref_dir = base / "references"
    output_dir = base / "output"
    latest_dir = base / "project_export" / "latest"
    prompt_path = base / "prompt.txt"

    meta["has_source"] = (input_dir / "building.png").exists()
    meta["has_style"] = (ref_dir / "style_reference_target.png").exists()
    meta["has_final"] = (output_dir / "final_imported_render.png").exists()
    meta["has_light_map"] = (latest_dir / "02_light_plan_reference.png").exists()
    meta["ies_count"] = len([p for p in ies_dir.glob("*") if p.is_file() and p.suffix.lower() == ".ies"]) if ies_dir.exists() else 0
    meta["source_name"] = meta.get("source_name") or ("building.png" if meta["has_source"] else "")
    meta["style_name"] = meta.get("style_name") or ("style_reference_target.png" if meta["has_style"] else "")
    meta["prompt_preview"] = ""
    if prompt_path.exists():
        prompt = prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
        meta["prompt_preview"] = prompt[:220] + ("..." if len(prompt) > 220 else "")
    meta["render_history"] = meta.get("render_history") or []
    project_learning_path = base / "learning_events.jsonl"
    meta["learning_events_count"] = 0
    if project_learning_path.exists():
        meta["learning_events_count"] = len([
            line for line in project_learning_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        ])
    return meta


async def save_upload(upload: UploadFile, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return target


def ies_photo_path(ies_path: Path) -> Path | None:
    if not ies_path.exists() or ies_path.suffix.lower() != ".ies":
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = ies_path.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def ies_catalog_photo(ies_path: Path) -> Path | None:
    if not ies_path.exists():
        return None
    local = ies_photo_path(ies_path)
    if local:
        return local
    return product_photo_for_ies_name(ies_path.name)


def list_ies_files(folder: Path) -> list[dict]:
    items = list_files(folder, {".ies"})
    for item in items:
        photo = ies_catalog_photo(folder / item["relative_path"])
        item["has_photo"] = bool(photo)
        if photo:
            item["photo_name"] = photo.name
    return items


def copy_ies_with_photo(src_ies: Path, dst_dir: Path) -> Path:
    copied = copy_unique(src_ies, dst_dir, src_ies.name)
    photo = ies_catalog_photo(src_ies)
    if photo:
        copy_unique(photo, dst_dir, copied.with_suffix(photo.suffix).name)
    return copied


def list_files(folder: Path, exts: set[str] | None = None) -> list[dict]:
    if not folder.exists():
        return []
    result = []
    seen_hashes = set()
    for path in sorted(folder.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file():
            continue
        if exts and path.suffix.lower() not in exts:
            continue
        digest = file_digest(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        result.append({
            "name": path.name,
            "relative_path": str(path.relative_to(folder)).replace("\\", "/"),
            "size": path.stat().st_size,
            "sha256": digest,
        })
    return result


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def same_file_content(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and file_digest(a) == file_digest(b)
    except OSError:
        return False


def copy_unique(src: Path, dst_dir: Path, preferred_name: str | None = None) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for existing in dst_dir.rglob("*"):
        if existing.is_file() and same_file_content(src, existing):
            return existing

    name = safe_name(preferred_name or src.name)
    target = dst_dir / name
    if not target.exists():
        shutil.copy2(src, target)
        return target

    stem = target.stem
    suffix = target.suffix
    index = 2
    while True:
        candidate = dst_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            return candidate
        index += 1


def resolve_ies_source(filename: str) -> Path | None:
    wanted = safe_name(filename).lower()
    for folder in (ROOT / "ies_library", ROOT / "examples" / "ies", IES_LIBRARY_DIR):
        if not folder.exists():
            continue
        for path in folder.rglob("*.ies"):
            if path.name == filename or safe_name(path.name).lower() == wanted:
                return path
        candidate = folder / filename
        if candidate.exists():
            return candidate
    return None


def library_root(kind: Literal["source", "ies", "style"]) -> Path:
    return {"source": SOURCE_LIBRARY_DIR, "ies": IES_LIBRARY_DIR, "style": STYLE_LIBRARY_DIR}[kind]


def resolve_library_file(kind: Literal["source", "ies", "style"], relative_path: str) -> Path:
    root = library_root(kind).resolve()
    target = (root / relative_path).resolve()
    if not str(target).startswith(str(root)) or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Library file not found")
    return target


def _require_catalog_password(password: str) -> None:
    if not CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Каталог отключён: не задан пароль администратора")
    if (password or "").strip() != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Неверный пароль")


def _fixture_dir_by_id(fixture_id: str) -> Path:
    fid = safe_name(fixture_id).strip()
    if not fid:
        raise HTTPException(status_code=400, detail="Invalid fixture id")
    return (FIXTURES_LIBRARY_DIR / fid).resolve()


def list_fixtures() -> list[dict]:
    items = []
    if not FIXTURES_LIBRARY_DIR.exists():
        return items
    for folder in sorted([p for p in FIXTURES_LIBRARY_DIR.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        meta_path = folder / "meta.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        photo = next((p for p in (folder / "photo").parent.glob("photo.*") if p.is_file()), None)
        # Нормализуем: допускаем photo.jpg/png/webp и profile.ies
        photo = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = folder / f"photo{ext}"
            if p.exists():
                photo = p
                break
        ies = folder / "profile.ies"
        items.append({
            "id": folder.name,
            "name": meta.get("name") or folder.name,
            "has_photo": bool(photo and photo.exists()),
            "has_ies": bool(ies.exists()),
        })
    return items


def import_existing_to_library() -> dict:
    sources = [
        (ROOT / "examples" / "source_photos", SOURCE_LIBRARY_DIR, IMAGE_EXTS),
        (ROOT / "input", SOURCE_LIBRARY_DIR, IMAGE_EXTS),
        (VIZ_EXAMPLES_DIR, SOURCE_LIBRARY_DIR / "auto_test", IMAGE_EXTS),
        (ROOT / "examples" / "style_references", STYLE_LIBRARY_DIR, IMAGE_EXTS),
        (ROOT / "references", STYLE_LIBRARY_DIR, IMAGE_EXTS),
    ]
    counts = {"source": 0, "ies": 0, "style": 0}
    for src_dir, dst_dir, exts in sources:
        if not src_dir.exists():
            continue
        for src in src_dir.rglob("*"):
            if src.is_file() and src.suffix.lower() in exts:
                copy_unique(src, dst_dir, src.name)
                if dst_dir == SOURCE_LIBRARY_DIR:
                    counts["source"] += 1
                elif dst_dir == STYLE_LIBRARY_DIR:
                    counts["style"] += 1
    counts["ies"] = bootstrap_ies_catalog()
    return counts


def routerai_key() -> str:
    key = os.environ.get("ROUTERAI_API_KEY", "").strip()
    if key:
        return key
    key_path = ROOT / "routerai_api_key.txt"
    if key_path.exists():
        return key_path.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def routerai_model() -> str:
    model = os.environ.get("ROUTERAI_IMAGE_MODEL", "").strip()
    if model:
        return model
    model_path = ROOT / "routerai_model.txt"
    if model_path.exists():
        text = model_path.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            return text
    return "google/gemini-3.1-flash-image-preview"


def resolve_routerai_model(override: str = "") -> str:
    candidate = (override or "").strip()
    if candidate:
        candidate = ROUTERAI_MODEL_ALIASES.get(candidate, candidate)
    allowed = {item["id"] for item in ROUTERAI_IMAGE_MODELS}
    allowed |= set(ROUTERAI_MODEL_ALIASES.keys())
    if candidate and candidate in allowed:
        return ROUTERAI_MODEL_ALIASES.get(candidate, candidate)
    return routerai_model()


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def image_aspect_ratio(path: Path) -> str:
    """Подбираем aspect_ratio API под исходное фото, иначе модель перекадрирует кадр."""
    with Image.open(path) as img:
        w, h = img.size
    if w <= 0 or h <= 0:
        return "16:9"
    ratio = w / h
    options = [
        ("1:1", 1.0),
        ("4:5", 4 / 5),
        ("5:4", 5 / 4),
        ("3:4", 3 / 4),
        ("4:3", 4 / 3),
        ("2:3", 2 / 3),
        ("3:2", 3 / 2),
        ("9:16", 9 / 16),
        ("16:9", 16 / 9),
    ]
    return min(options, key=lambda item: abs(item[1] - ratio))[0]


def resolve_output_aspect(base: Path | None, image_paths: list[Path]) -> str:
    if base is not None:
        for candidate in (
            base / "project_export" / "latest" / "01_source_building.png",
            base / "input" / "building.png",
        ):
            if candidate.exists():
                return image_aspect_ratio(candidate)
    for path in image_paths:
        if path.exists():
            return image_aspect_ratio(path)
    return "16:9"


def save_response_image(value: str, out_path: Path) -> Path:
    if value.startswith("data:"):
        raw = base64.b64decode(value.split(",", 1)[1])
    else:
        with urllib.request.urlopen(value, timeout=240) as response:
            raw = response.read()

    tmp = out_path.with_suffix(".tmp")
    tmp.write_bytes(raw)
    try:
        save_rgb(tmp, out_path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return out_path


def save_data_url(value: str, out_path: Path) -> Path:
    if not value or not value.startswith("data:"):
        raise RuntimeError("Expected data URL")
    raw = base64.b64decode(value.split(",", 1)[1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw)
    return out_path


def save_annotation_upload(upload: UploadFile | None, data_url: str, out_path: Path) -> Path | None:
    """Сохранить разметку из файла или data-URL; сжать/уменьшить перед отправкой в AI."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    raw: bytes | None = None
    if upload is not None:
        raw = upload.file.read()
    elif data_url and data_url.startswith("data:"):
        raw = base64.b64decode(data_url.split(",", 1)[1])
    if not raw:
        return None
    tmp.write_bytes(raw)
    try:
        img = Image.open(tmp).convert("RGBA")
        max_side = 1600
        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        img.save(out_path, format="PNG", optimize=True)
    except Exception:
        shutil.copy2(tmp, out_path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return out_path if out_path.exists() else None


def analyze_markup_colors(annotation_path: Path) -> dict:
    """Classify paint strokes as cyan(remove) vs red(change)."""
    result = {
        "has_cyan": False,
        "has_red": False,
        "cyan_pixels": 0,
        "red_pixels": 0,
        "mode": "",  # remove | change | mixed | ""
    }
    if not annotation_path or not Path(annotation_path).exists():
        return result
    try:
        with Image.open(annotation_path).convert("RGBA") as img:
            # Downsample for speed
            max_side = 640
            w, h = img.size
            scale = min(1.0, max_side / max(w, h))
            if scale < 1.0:
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
            px = img.load()
            ww, hh = img.size
            cyan = red = 0
            step = 2 if max(ww, hh) > 400 else 1
            for y in range(0, hh, step):
                for x in range(0, ww, step):
                    r, g, b, a = px[x, y]
                    if a < 20:
                        continue
                    # Cyan/aqua: G and B dominate R
                    if g >= r + 15 and b >= r + 10 and g + b > r * 2:
                        cyan += 1
                    # Red/orange: R dominates
                    elif r >= g + 20 and r >= b + 20:
                        red += 1
            result["cyan_pixels"] = cyan
            result["red_pixels"] = red
            result["has_cyan"] = cyan >= 8
            result["has_red"] = red >= 8
            if result["has_cyan"] and result["has_red"]:
                result["mode"] = "mixed"
            elif result["has_cyan"]:
                result["mode"] = "remove"
            elif result["has_red"]:
                result["mode"] = "change"
    except Exception:
        pass
    return result


def blend_edit_with_markup_mask(
    original_path: Path,
    edited_path: Path,
    annotation_path: Path,
    *,
    mode: str = "",
) -> dict:
    """Hard-lock edits to painted zones: outside mask keep original pixels.

    The generative model only gets soft prompt guidance; this post-pass prevents
    accidental changes to unmarked luminaires/facade areas.
    """
    info = {"ok": False, "dilate": 0, "feather": 0, "mode": mode or ""}
    if not (original_path.exists() and edited_path.exists() and annotation_path.exists()):
        return info
    try:
        with Image.open(original_path).convert("RGB") as original:
            with Image.open(edited_path).convert("RGB") as edited:
                with Image.open(annotation_path).convert("RGBA") as ann:
                    if edited.size != original.size:
                        edited = edited.resize(original.size, Image.Resampling.LANCZOS)
                    if ann.size != original.size:
                        ann = ann.resize(original.size, Image.Resampling.LANCZOS)
                    alpha = ann.split()[-1]
                    # Binary paint presence
                    mask = alpha.point(lambda v: 255 if v >= 18 else 0)
                    # Dilate so nearby beam/fixture body under a stroke is included.
                    # Remove needs a bit more room for uplight cones.
                    dilate_rounds = 5 if (mode or "") == "remove" else 3
                    if (mode or "") == "place" or (mode or "") == "change":
                        dilate_rounds = 4
                    for _ in range(max(1, dilate_rounds)):
                        mask = mask.filter(ImageFilter.MaxFilter(9))
                    # Extra upward expansion for projector beams (remove/change)
                    if (mode or "") in {"remove", "change", "mixed", "place"}:
                        up = Image.new("L", mask.size, 0)
                        shift = max(18, original.size[1] // 28)
                        up.paste(mask, (0, -shift))
                        mask = ImageChops.lighter(mask, up)
                    feather = 10 if (mode or "") == "remove" else 8
                    if feather > 0:
                        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
                    # White mask => take edited; black => keep original
                    blended = Image.composite(edited, original, mask)
                    blended.save(edited_path, quality=95)
                    try:
                        mask.convert("L").save(edited_path.parent / "edit_blend_mask.png")
                    except Exception:
                        pass
                    info.update({"ok": True, "dilate": dilate_rounds, "feather": feather})
    except Exception as exc:
        info["error"] = str(exc)
    return info


def extract_routerai_image(response_json: dict, out_path: Path) -> Path:
    choices = response_json.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        for image in message.get("images") or []:
            image_url = image.get("image_url") or {}
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if url:
                return save_response_image(url, out_path)

        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                image_url = part.get("image_url") or part.get("image")
                if isinstance(image_url, dict) and image_url.get("url"):
                    return save_response_image(image_url["url"], out_path)
                if isinstance(image_url, str):
                    return save_response_image(image_url, out_path)

    raise RuntimeError("RouterAI response does not contain an image")


def is_finetuned_model(model: str) -> bool:
    mid = resolve_routerai_model(model) if model else ""
    return mid == FINETUNED_MODEL_ID or (model or "").strip() == FINETUNED_MODEL_ID


def soft_finetune_prompt(prompt: str) -> str:
    from finetune import TRIGGER_TOKEN
    head = (
        f"NITEOS fine-tuned mode ({TRIGGER_TOKEN}, soft few-shot). "
        "Image 1 = source facade (keep identity 1:1). "
        "Following image(s) = lighting LOOK references only: transfer rhythm, fixture language and night quality — "
        "do NOT copy their architecture. "
        "Prefer realistic projector/linear facade lighting; do not invent pilasters or remove signs.\n\n"
    )
    body = (prompt or "").strip()
    if TRIGGER_TOKEN not in body:
        body = f"{TRIGGER_TOKEN}. {body}"
    return head + body


def call_routerai(
    prompt: str,
    image_paths: list[Path],
    out_path: Path,
    aspect_ratio: str | None = None,
    project_base: Path | None = None,
    model: str = "",
) -> tuple[Path, dict]:
    chosen_aspect = aspect_ratio or resolve_output_aspect(project_base, image_paths)
    requested_model = resolve_routerai_model(model)
    soft_finetune = False

    if requested_model == FINETUNED_MODEL_ID:
        try:
            from finetune.client import finetuned_endpoint_configured, generate_finetuned_image
        except ImportError as exc:
            raise RuntimeError(f"Fine-tune client unavailable: {exc}") from exc
        if finetuned_endpoint_configured():
            return generate_finetuned_image(
                prompt,
                image_paths,
                out_path,
                aspect_ratio=chosen_aspect,
            )
        # Soft mode: fall through to Gemini with few-shot images already attached by render_project
        requested_model = SOFT_FINETUNE_BASE_MODEL
        prompt = soft_finetune_prompt(prompt)
        soft_finetune = True

    key = routerai_key()
    if not key:
        raise RuntimeError("RouterAI key is missing")

    content = [{"type": "text", "text": prompt}]
    used_images = []
    for path in image_paths:
        if path.exists():
            content.append({"type": "image_url", "image_url": {"url": image_data_url(path)}})
            used_images.append({
                "path": str(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
            })

    chosen_model = requested_model
    body = {
        "model": chosen_model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["text", "image"],
        "image_config": {"aspect_ratio": chosen_aspect, "image_size": "2K"},
    }
    api_log = {
        "model": body["model"],
        "endpoint": "https://routerai.ru/api/v1/chat/completions",
        "prompt": prompt,
        "images": used_images,
        "image_config": body["image_config"],
        "source_aspect_ratio": chosen_aspect,
        "modalities": body["modalities"],
        "prompt_chars": len(prompt),
        "requested_model": resolve_routerai_model(model),
        "soft_finetune": soft_finetune,
        "backend": "soft_finetune" if soft_finetune else "routerai",
    }
    request = urllib.request.Request(
        "https://routerai.ru/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            api_log["http_status"] = response.status
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="ignore")
        api_log["http_status"] = e.code
        api_log["error"] = details[:1200]
        raise RuntimeError(f"RouterAI error {e.code}: {details[:1200]}") from e

    api_log["response_summary"] = {
        "keys": list(data.keys()) if isinstance(data, dict) else [],
        "choices": len((data.get("choices") or [])) if isinstance(data, dict) else 0,
        "usage": data.get("usage") if isinstance(data, dict) else None,
    }
    result_path = extract_routerai_image(data, out_path)
    api_log["output"] = str(result_path)
    return result_path, api_log


def extract_routerai_text(response_json: dict) -> str:
    for choice in response_json.get("choices") or []:
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
            if parts:
                return "\n".join(parts).strip()
    raise RuntimeError("RouterAI response does not contain text")


def parse_json_model_response(text: str) -> dict:
    candidate = (text or "").strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not match:
            raise RuntimeError("Vision reviewer returned invalid JSON")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise RuntimeError("Vision reviewer JSON must be an object")
    return parsed


def call_routerai_vision_json(prompt: str, image_paths: list[Path], model: str = "") -> tuple[dict, dict]:
    key = routerai_key()
    if not key:
        raise RuntimeError("RouterAI key is missing")
    content = [{"type": "text", "text": prompt}]
    used_images = []
    for path in image_paths:
        if path.exists():
            content.append({"type": "image_url", "image_url": {"url": image_data_url(path)}})
            used_images.append({"name": path.name, "size_bytes": path.stat().st_size})
    chosen_model = (model or AUTO_REVIEW_CRITIC_MODEL or AUTO_REVIEW_ECONOMIC_CRITIC_MODEL).strip()
    body = {
        "model": chosen_model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 1800,
    }
    api_log = {
        "model": chosen_model,
        "endpoint": "https://routerai.ru/api/v1/chat/completions",
        "images": used_images,
        "prompt_chars": len(prompt),
        "kind": "vision_review",
    }
    request = urllib.request.Request(
        "https://routerai.ru/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
            api_log["http_status"] = response.status
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="ignore")
        api_log.update({"http_status": error.code, "error": details[:1200]})
        raise RuntimeError(f"RouterAI reviewer error {error.code}: {details[:1200]}") from error
    api_log["usage"] = data.get("usage") if isinstance(data, dict) else None
    text = extract_routerai_text(data)
    api_log["response_chars"] = len(text)
    return parse_json_model_response(text), api_log


def review_render_with_vision_agent(base: Path, final_path: Path, placement_plan: dict, critic_model: str = "") -> tuple[dict, dict]:
    source = base / "input" / "building.png"
    light_map = base / "project_export" / "latest" / "02_light_plan_reference.png"
    review_prompt = """You are an architectural lighting quality controller. Review the source facade photo and the generated night render. A third image, when present, is a light-plan reference. Compare the render only against the source facade, the selected lighting plan and the listed IES constraints. Do not judge artistic taste alone. Find missing repeated fixture zones, wrong placement on windows or unrelated surfaces, broken continuity, excessive glare, altered building geometry, or fixture types not supported by the plan. A style reference is optional and its absence is never an error.

Return JSON only, without markdown:
{
  "verdict": "pass" or "revise",
  "confidence": 0.0,
  "quality_score": 0,
  "issues": [{"type": "coverage|placement|geometry|glare|fixture_logic|style", "severity": "low|medium|high", "zone": "short location", "description": "short factual explanation"}],
  "revision_prompt": "a precise image-edit instruction, or empty string when verdict is pass"
}

Rules: verdict pass only when the lighting scheme is complete for the chosen scenario and building geometry is preserved. Use revise for material placement defects. Do not request another render for uncertain minor detail. Do not invent missing facade features.

Placement plan:
""" + json.dumps(placement_plan, ensure_ascii=False)[:12000]
    try:
        review, api_log = call_routerai_vision_json(
            review_prompt,
            [source, final_path, light_map],
            model=critic_model,
        )
    except Exception as error:
        return {
            "status": "unavailable",
            "verdict": "pass",
            "confidence": 0.0,
            "quality_score": 0,
            "issues": [],
            "revision_prompt": "",
            "error": str(error)[:500],
        }, {"kind": "vision_review", "error": str(error)[:1200]}

    verdict = str(review.get("verdict") or "pass").lower()
    if verdict not in {"pass", "revise"}:
        verdict = "pass"
    confidence = review.get("confidence", 0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    quality_score = review.get("quality_score", 0)
    try:
        quality_score = max(0, min(100, int(quality_score)))
    except (TypeError, ValueError):
        quality_score = 0
    issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    normalized_issues = [item for item in issues if isinstance(item, dict)][:8]
    revision_prompt = str(review.get("revision_prompt") or "").strip()[:4000]
    return {
        "status": "reviewed",
        "verdict": verdict,
        "confidence": confidence,
        "quality_score": quality_score,
        "issues": normalized_issues,
        "revision_prompt": revision_prompt,
    }, api_log


def review_profile_max_revisions(profile: str = "") -> int:
    profile = (profile or "economic").strip().lower()
    requested = 2 if profile == "full" else 1
    return min(requested, AUTO_REVIEW_MAX_REVISIONS)


def review_profile_critic_model(profile: str = "") -> str:
    if AUTO_REVIEW_CRITIC_MODEL:
        return AUTO_REVIEW_CRITIC_MODEL
    return AUTO_REVIEW_FULL_CRITIC_MODEL if (profile or "").strip().lower() == "full" else AUTO_REVIEW_ECONOMIC_CRITIC_MODEL


def automated_render_review_loop(base: Path, final_path: Path, placement_plan: dict, image_model: str, profile: str = "") -> dict:
    max_revisions = review_profile_max_revisions(profile)
    critic_model = review_profile_critic_model(profile)
    iterations = []
    for attempt in range(max_revisions + 1):
        review, review_log = review_render_with_vision_agent(base, final_path, placement_plan, critic_model)
        iteration = {"attempt": attempt, "review": review, "review_log": review_log}
        iterations.append(iteration)
        append_pipeline_log(base, "vision_review", iteration)
        should_revise = (
            review.get("status") == "reviewed"
            and review.get("verdict") == "revise"
            and review.get("confidence", 0) >= AUTO_REVIEW_MIN_CONFIDENCE
            and bool(review.get("revision_prompt"))
            and attempt < max_revisions
        )
        if not should_revise:
            break
        save_render_history_entry(base, kind="auto_candidate", note=review["revision_prompt"])
        revision_prompt = (
            "Revise the current night architectural lighting render according to the quality-controller instruction below. "
            "Preserve the exact building geometry, windows, materials, framing, camera angle, and all correct existing lighting. "
            "Only correct the listed lighting defects. Do not add text, logos, red marks, unrelated fixtures, or new architecture.\n"
            f"Quality-controller instruction: {review['revision_prompt']}"
        )
        _, revision_log = call_routerai(
            revision_prompt,
            [final_path, base / "input" / "building.png"],
            final_path,
            project_base=base,
            model=image_model,
        )
        iteration["revision_applied"] = True
        iteration["revision_log"] = revision_log
        append_pipeline_log(base, "auto_revision", {"attempt": attempt + 1, "review": review, "api": revision_log})
        apply_niteos_watermark(final_path)
    final_review = iterations[-1]["review"] if iterations else {}
    return {
        "profile": (profile or "economic").strip().lower(),
        "critic_model": critic_model,
        "max_revisions": max_revisions,
        "revisions_applied": sum(1 for item in iterations if item.get("revision_applied")),
        "final_review": final_review,
        "iterations": iterations,
    }


def run_packager(base: Path) -> dict:
    env = os.environ.copy()
    env["NITEOS_BASE_DIR"] = str(base)
    result = subprocess.run(
        [sys.executable, str(ROOT / "ai_packager_v29.py")],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    packager_log = {
        "returncode": result.returncode,
        "stdout": (result.stdout or "")[-3000:],
        "stderr": (result.stderr or "")[-3000:],
    }
    if result.returncode != 0:
        packager_log["error"] = (result.stderr or result.stdout or "Packager failed").strip()
        raise RuntimeError(packager_log["error"])
    return packager_log


def collect_packager_artifacts(base: Path) -> dict:
    latest = base / "project_export" / "latest"
    artifacts = {
        "latest_dir": str(latest),
        "files": list_files(latest) if latest.exists() else [],
    }
    for name in (
        "04_prompt_for_chatgpt.txt",
        "05_prompt_for_gemini_nano_banana.txt",
        "07_ies_summary.txt",
        "08_equipment_draft.md",
    ):
        path = latest / name
        if path.exists():
            artifacts[name] = path.read_text(encoding="utf-8", errors="ignore")
    return artifacts


def read_ai_prompt(latest: Path) -> tuple[str, str]:
    chatgpt_path = latest / "04_prompt_for_chatgpt.txt"
    if chatgpt_path.exists():
        return chatgpt_path.read_text(encoding="utf-8", errors="ignore"), chatgpt_path.name
    gemini_path = latest / "05_prompt_for_gemini_nano_banana.txt"
    if gemini_path.exists():
        return gemini_path.read_text(encoding="utf-8", errors="ignore"), gemini_path.name
    raise RuntimeError("Prompt file not found in project_export/latest")


def project_ies_names(base: Path) -> list[str]:
    ies_dir = base / "ies_library"
    if not ies_dir.exists():
        return []
    return sorted(
        p.name for p in ies_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".ies"
    )


def parse_ies_photometry(path: Path) -> dict:
    """Read the small, reliable subset of LM-63 needed for placement decisions."""
    result = {"filename": path.name, "parsed": False}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        tilt_index = next(index for index, line in enumerate(lines) if line.strip().upper().startswith("TILT="))
        header = {}
        for line in lines[:tilt_index]:
            match = re.match(r"\[([^\]]+)\]\s*(.*)", line.strip())
            if match:
                header[match.group(1).lower()] = match.group(2).strip()
        values = [float(item) for item in re.findall(r"[-+]?(?:\d+\.\d+|\d+|\.\d+)", " ".join(lines[tilt_index + 1:]))]
        if len(values) < 14:
            return result
        lamp_count = max(1, int(values[0]))
        lumens_per_lamp = values[1]
        candela_multiplier = values[2]
        vertical_count = int(values[3])
        horizontal_count = int(values[4])
        width, length, height = values[7:10]
        angles_offset = 13
        vertical_angles = values[angles_offset:angles_offset + vertical_count]
        candela_offset = angles_offset + vertical_count + horizontal_count
        candelas = values[candela_offset:candela_offset + vertical_count]
        if len(vertical_angles) != vertical_count or len(candelas) != vertical_count:
            return result
        scaled = [max(0.0, value * candela_multiplier) for value in candelas]
        peak = max(scaled) if scaled else 0.0
        half_peak = peak * 0.5
        half_angles = [angle for angle, value in zip(vertical_angles, scaled) if value >= half_peak]
        beam_angle = round(max(half_angles) - min(half_angles), 1) if len(half_angles) >= 2 else 0.0
        beam_class = "narrow" if beam_angle and beam_angle < 30 else ("medium" if beam_angle and beam_angle < 70 else "wide")
        dimensions = [abs(width), abs(length), abs(height)]
        optical_form = "linear" if max(dimensions) >= 0.5 and min(dimensions) <= 0.25 else "compact"
        result.update({
            "parsed": True,
            "luminaire": header.get("luminaire") or header.get("lumcat") or path.stem,
            "lamp_count": lamp_count,
            "nominal_lumens": round(lamp_count * lumens_per_lamp),
            "peak_candela": round(peak, 1),
            "beam_angle_deg": beam_angle,
            "beam_class": beam_class,
            "optical_form": optical_form,
            "dimensions_m": {"width": round(width, 3), "length": round(length, 3), "height": round(height, 3)},
        })
    except (OSError, ValueError, StopIteration):
        return result
    return result


def project_ies_photometry(base: Path) -> list[dict]:
    ies_dir = base / "ies_library"
    if not ies_dir.exists():
        return []
    return [parse_ies_photometry(path) for path in sorted(ies_dir.glob("*.ies"))]


def photometric_placement_rules(items: list[dict]) -> list[str]:
    parsed = [item for item in items if item.get("parsed")]
    if not parsed:
        return ["IES photometry was not parsed; use the selected product logic conservatively and do not invent a different fixture type."]
    rules: list[str] = []
    beam_classes = {item.get("beam_class") for item in parsed}
    forms = {item.get("optical_form") for item in parsed}
    if "narrow" in beam_classes:
        rules.append("Selected IES includes narrow optics: repeat fixtures at a deliberate facade rhythm with overlapping beam edges, avoiding isolated bright cones and dark bays.")
    if "wide" in beam_classes:
        rules.append("Selected IES includes wide optics: use fewer, balanced positions and avoid over-layering broad wash that would flatten facade relief.")
    if "linear" in forms:
        rules.append("Selected IES describes a linear luminaire: keep it as continuous or aligned linear runs along the chosen architectural bands, not as scattered point spots.")
    if "compact" in forms and "linear" not in forms:
        rules.append("Selected IES describes compact optics: mount discrete fixtures in a repeatable architectural rhythm rather than drawing uninterrupted luminous strips.")
    return rules


def ensure_latest_source_copy(base: Path) -> Path:
    source = base / "input" / "building.png"
    if not source.exists():
        raise RuntimeError("Source photo missing")
    latest = base / "project_export" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    dest = latest / "01_source_building.png"
    if not dest.exists() or dest.stat().st_mtime < source.stat().st_mtime:
        save_rgb(source, dest)
    return source


def prepare_agent_render_prompt(
    base: Path,
    *,
    prompt_override: str = "",
    facade_mode_override: str = "",
    router_model: str = "",
) -> dict:
    prompt_path = base / "prompt.txt"
    user_prompt = prompt_override.strip() or (prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else "")
    facade_mode = facade_mode_override.strip() or read_facade_mode(base)
    chosen_model = resolve_routerai_model(router_model)
    prompt = user_prompt.strip()
    generated_from_scenario = False
    if not prompt:
        meta = read_project_meta(base)
        scenario_id = (meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "").strip()
        if scenario_id:
            try:
                scenario = client_scenario_by_id(scenario_id)
                product_id = (
                    meta.get("dealer_product_id")
                    or meta.get("client_product_id")
                    or product_id_for_scenario(scenario)
                )
                product = client_product_by_id(product_id)
                prompt = build_dealer_scenario_prompt(scenario, product, base, facade_mode)
                generated_from_scenario = bool(prompt)
            except HTTPException:
                prompt = ""
        if not prompt:
            raise RuntimeError("Prompt is empty — select a scenario or enter an instruction")

    meta = read_project_meta(base)
    is_auto_viz = (
        (meta.get("work_mode") or "").strip().lower() == "auto"
        and bool(str(meta.get("auto_viz_ref") or "").strip())
    )
    if is_auto_viz:
        # Auto = transfer lighting from the chosen viz example; skip scenario placement memory.
        placement_candidates = []
        placement_plan = {
            "family": "auto_viz_transfer",
            "candidate_id": "auto_viz",
            "strategy": "style_reference_transfer",
            "score": {},
        }
        planned_prompt = (
            prompt.rstrip()
            + "\n\n"
            + PROMPT_AUTO_FACADE_HARD_RULES
            + "\n\nIMAGE ORDER:\n"
            "1) source facade — keep identity.\n"
            "2) lighting look reference — transfer light language only.\n"
            "Final frame must remain recognizably Image 1 at night.\n"
        )
    else:
        placement_candidates = build_placement_candidates(base, prompt)
        placement_plan = placement_candidates[0] if placement_candidates else build_placement_plan(base, prompt)
        planned_prompt = append_placement_plan_to_prompt(prompt, placement_plan)
        planned_prompt = planned_prompt.rstrip() + "\n\n" + PROMPT_AUTO_FACADE_HARD_RULES + "\n"
    render_prompt, learning_guidance = build_learning_guidance(base, planned_prompt, placement_plan=placement_plan)
    render_prompt = append_facade_identity_lock(render_prompt)
    return {
        "user_prompt": user_prompt,
        "base_prompt": prompt,
        "render_prompt": render_prompt,
        "generated_from_scenario": generated_from_scenario,
        "placement_plan": placement_plan,
        "placement_candidates": placement_candidates,
        "learning_guidance": learning_guidance,
        "prompt_chars": len(render_prompt),
        "facade_mode": facade_mode,
        "routerai_model": chosen_model,
    }


def render_project(base: Path, router_model: str = "", review_profile: str = "economic") -> Path:
    prompt_path = base / "prompt.txt"
    user_prompt = prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else ""
    facade_mode = read_facade_mode(base)
    chosen_model = resolve_routerai_model(router_model)
    agent_preview = prepare_agent_render_prompt(base, router_model=chosen_model)
    user_prompt = agent_preview["user_prompt"]
    prompt = agent_preview["base_prompt"]
    render_prompt = agent_preview["render_prompt"]
    placement_plan = agent_preview["placement_plan"]
    placement_candidates = agent_preview["placement_candidates"]
    learning_guidance = agent_preview["learning_guidance"]
    if agent_preview.get("generated_from_scenario"):
        prompt_path.write_text(prompt, encoding="utf-8")
    append_pipeline_log(base, "render_start", {
        "user_prompt": user_prompt,
        "facade_mode": facade_mode,
        "routerai_model": chosen_model,
        "ies_files": [p.name for p in sorted((base / "ies_library").glob("*")) if p.is_file()],
        "has_source": (base / "input" / "building.png").exists(),
        "input_mode": "source_photo_only",
    })

    prompt = agent_preview["base_prompt"]
    if False and not prompt:
        meta = read_project_meta(base)
        scenario_id = (meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "").strip()
        if scenario_id:
            try:
                scenario = client_scenario_by_id(scenario_id)
                product_id = (
                    meta.get("dealer_product_id")
                    or meta.get("client_product_id")
                    or product_id_for_scenario(scenario)
                )
                product = client_product_by_id(product_id)
                prompt = build_dealer_scenario_prompt(scenario, product, base, facade_mode)
            except HTTPException:
                prompt = ""
        if not prompt:
            raise RuntimeError("Prompt is empty — выберите сценарий или введите задание")
        prompt_path.write_text(prompt, encoding="utf-8")

    append_pipeline_log(base, "placement_candidates", {
        "selected_candidate_id": placement_plan.get("candidate_id", ""),
        "selected_score": placement_plan.get("score", {}),
        "candidates": [
            {
                "candidate_id": item.get("candidate_id", ""),
                "strategy": item.get("strategy", ""),
                "family": item.get("family", ""),
                "score": item.get("score", {}),
                "strategy_memory": item.get("strategy_memory", {}),
            }
            for item in placement_candidates
        ],
    })
    append_pipeline_log(base, "placement_plan", placement_plan)

    append_pipeline_log(base, "learning_guidance", learning_guidance)

    meta_pre = read_project_meta(base)
    style_ref = base / "references" / "style_reference_target.png"
    use_style_ref = (
        (meta_pre.get("work_mode") or "").strip().lower() == "auto"
        and style_ref.exists()
        and bool(str(meta_pre.get("auto_viz_ref") or "").strip())
    )
    input_images = ["input/building.png"]
    if use_style_ref:
        input_images.append("references/style_reference_target.png")
    append_pipeline_log(base, "prompt_prepared", {
        "prompt": render_prompt,
        "prompt_source": "prompt.txt",
        "input_images": input_images,
        "placement_plan_family": placement_plan.get("family", ""),
        "learning_applied": learning_guidance.get("applied", False),
        "auto_viz_ref": meta_pre.get("auto_viz_ref") or "",
    })

    source = ensure_latest_source_copy(base)
    images = [source]
    if use_style_ref:
        images.append(prepare_image_for_vision(style_ref, max_side=1600))
    soft_finetune_refs: list[str] = []
    if chosen_model == FINETUNED_MODEL_ID:
        try:
            from finetune.client import finetuned_endpoint_configured
            from finetune.export_dataset import list_fewshot_targets
            if not finetuned_endpoint_configured():
                for ref in list_fewshot_targets(2):
                    prepared = prepare_image_for_vision(ref, max_side=1400)
                    images.append(prepared)
                    soft_finetune_refs.append(str(ref))
                    input_images.append(f"fewshot:{ref.name}")
        except Exception as exc:
            append_pipeline_log(base, "soft_finetune_refs_error", {"error": str(exc)})

    final_path = base / "output" / "final_imported_render.png"
    _, api_log = call_routerai(
        render_prompt,
        images,
        final_path,
        project_base=base,
        model=chosen_model,
    )
    if soft_finetune_refs:
        api_log["soft_finetune_refs"] = soft_finetune_refs
    append_pipeline_log(base, "routerai_render", api_log)
    apply_niteos_watermark(final_path)
    # Single-stage render: auto vision re-generation is disabled
    automatic_review = {
        "enabled": False,
        "skipped": True,
        "profile": (review_profile or "economic").strip().lower(),
        "revisions_applied": 0,
        "reason": "single_stage_render",
    }
    render_audit = audit_render_coverage(base, final_path, placement_plan)
    append_pipeline_log(base, "render_audit", render_audit)
    ies_used = project_ies_names(base)
    ies_summary_path = base / "project_export" / "latest" / "07_ies_summary.txt"
    ies_summary_preview = ""
    if ies_summary_path.exists():
        ies_summary_preview = ies_summary_path.read_text(encoding="utf-8", errors="ignore")[:400].strip()
    meta = read_project_meta(base)
    render_product_name = (
        meta.get("dealer_product_name")
        or meta.get("client_product_name")
        or infer_product_name_from_ies(ies_used)
    )
    render_product_id = meta.get("dealer_product_id") or meta.get("client_product_id") or ""
    render_ies_items = build_render_ies_items(base, ies_used, render_product_id, render_product_name)
    write_project_meta(base, {
        "routerai_model": chosen_model,
        "last_placement_plan": placement_plan,
        "last_placement_candidates": [
            {
                "candidate_id": item.get("candidate_id", ""),
                "strategy": item.get("strategy", ""),
                "family": item.get("family", ""),
                "score": item.get("score", {}),
                "strategy_memory": item.get("strategy_memory", {}),
            }
            for item in placement_candidates
        ],
        "learning_guidance": learning_guidance,
        "last_render_audit": render_audit,
        "render_ies_files": ies_used,
        "render_ies_items": render_ies_items,
        "render_ies_summary": ies_summary_preview,
        "render_product_id": render_product_id,
        "render_product_name": render_product_name,
        "render_scenario_id": meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "",
        "render_scenario_name": meta.get("dealer_scenario_name") or meta.get("client_scenario_name") or "",
        "render_legacy_ref": meta.get("dealer_legacy_ref") or "",
    })
    history_entry = save_render_history_entry(
        base,
        kind=render_history_kind(base),
        note=(render_prompt[:220] + "...") if len(render_prompt) > 220 else render_prompt,
        prompt=render_prompt,
    )
    write_project_meta(base, {
        "status": "rendered",
        "final": "output/final_imported_render.png",
        "routerai_model": chosen_model,
        "last_history_entry": history_entry,
        "last_placement_plan": placement_plan,
        "last_placement_candidates": [
            {
                "candidate_id": item.get("candidate_id", ""),
                "strategy": item.get("strategy", ""),
                "family": item.get("family", ""),
                "score": item.get("score", {}),
                "strategy_memory": item.get("strategy_memory", {}),
            }
            for item in placement_candidates
        ],
        "learning_guidance": learning_guidance,
        "last_render_audit": render_audit,
        "automatic_review": automatic_review,
        "feedback_required": True,
        "render_ies_files": ies_used,
        "render_ies_items": render_ies_items,
        "render_ies_summary": ies_summary_preview,
        "render_product_id": render_product_id,
        "render_product_name": render_product_name,
        "render_scenario_id": meta.get("dealer_scenario_id") or meta.get("client_scenario_id") or "",
        "render_scenario_name": meta.get("dealer_scenario_name") or meta.get("client_scenario_name") or "",
        "render_legacy_ref": meta.get("dealer_legacy_ref") or "",
    })
    append_learning_event(base, "render_created", payload={
        "history_entry": history_entry,
        "ies_summary": ies_summary_preview,
        "ies_used": ies_used,
        "placement_plan": placement_plan,
        "learning_guidance": learning_guidance,
        "render_audit": render_audit,
        "automatic_review": automatic_review,
        "generation_archive": (history_entry or {}).get("generation_archive") or "",
    })
    return final_path


def edit_project_render(
    base: Path,
    instruction: str,
    annotation_data_url: str | None = None,
    annotation_upload: UploadFile | None = None,
    router_model: str = "",
    markup_contract: str = "",
    history_kind: str = "edit",
    annotation_path: Path | None = None,
) -> Path:
    final_path = base / "output" / "final_imported_render.png"
    if not final_path.exists():
        raise RuntimeError("Final render is missing")

    images = [final_path]
    saved_annotation = None
    guide_path = None
    markup_colors: dict = {}

    if annotation_path is not None and Path(annotation_path).exists():
        saved_annotation = Path(annotation_path)
    elif annotation_upload is not None or (annotation_data_url and annotation_data_url.startswith("data:")):
        out_ann = base / "output" / "edit_annotation.png"
        saved_annotation = save_annotation_upload(annotation_upload, annotation_data_url or "", out_ann)

    if saved_annotation is not None and saved_annotation.exists():
        markup_colors = analyze_markup_colors(saved_annotation)
        mode = str(markup_colors.get("mode") or "")
        # Composite marks onto a copy of the final so the model sees exact luminaire locations.
        guide_path = base / "output" / "edit_markup_guide.png"
        try:
            with Image.open(final_path).convert("RGBA") as base_img:
                with Image.open(saved_annotation).convert("RGBA") as mask_img:
                    if mask_img.size != base_img.size:
                        mask_img = mask_img.resize(base_img.size, Image.Resampling.LANCZOS)
                    r, g, b, a = mask_img.split()
                    a = a.point(lambda v: min(255, int(v * 1.35)) if v >= 12 else 0)
                    mask_img = Image.merge("RGBA", (r, g, b, a))
                    guide = Image.alpha_composite(base_img, mask_img)
                    guide.convert("RGB").save(guide_path, quality=95)
            images.append(guide_path)
            # Do NOT also send transparent mask as a 3rd image — it confuses removal scope.
        except Exception:
            images.append(saved_annotation)
            guide_path = None

        # Force instruction to match paint colors (overrides vague «убери или измени»).
        user_note = (instruction or "").strip()
        place = False
        try:
            from vision_agent.chat_agent import wants_place_fixture
            place = wants_place_fixture(user_note)
        except Exception:
            place = any(
                k in user_note.lower()
                for k in ("place", "projector", "простав", "постав", "добав", "размест", "установ", "прожект")
            )
        if mode == "remove":
            instruction = (
                "REMOVE ONLY the luminaires and light beams under CYAN paint marks. "
                "Do not remove, dim, or redesign any unmarked luminaire — copy them from Image 1. "
                "Do not darken facade panels."
            )
        elif mode == "change" and place:
            instruction = (
                "PLACE/ADD the requested architectural luminaire ONLY inside RED paint marks "
                "(e.g. projector uplight / linear / wash) with a realistic beam matching the scene. "
                "Do not invent fixtures outside red marks. "
                "Do not remove or redesign unmarked luminaires — copy them from Image 1. "
                "Do not invent new architecture or darken facade panels."
            )
        elif mode == "change":
            instruction = (
                "CHANGE/REWORK ONLY the luminaires or beams under RED paint marks "
                "(or place/add a fixture there if the user asks). "
                "Do not remove or redesign any unmarked luminaire — copy them from Image 1. "
                "Do not darken facade panels."
            )
        elif mode == "mixed":
            instruction = (
                "CYAN marks = remove those luminaires+beams; "
                "RED marks = change existing luminaires OR place/add a fixture if the user asks. "
                "Do not touch any unmarked luminaire — copy them from Image 1."
            )
        else:
            instruction = (
                "Edit ONLY under paint marks (cyan=remove, red=change or place if asked). "
                "Leave unmarked luminaires identical to Image 1."
            )
        if user_note:
            instruction = f"{instruction} User request: {user_note}"

    prompt = (
        "Доработай ночной рендер архитектурной подсветки по инструкции. "
        "Сохранить геометрию здания, окна, ворота, материалы, пропорции и все штатные элементы фасада. "
        "Не удалять дорожные знаки, таблички, наклейки, камеры и светофоры. "
        "ЗАПРЕЩЕНО дорисовывать новые пилястры, колонны, простенки и архитектурные выступы — менять только свет. "
        "CRITICAL: edit ONLY architectural luminaires under paint marks "
        "(or ADD a fixture inside a RED mark when the user asks to place/install one). "
        "NEVER change unmarked luminaires. NEVER darken, black out, or retexture facade panels. "
        "When removing a marked light, restore the wall like neighboring unmarked panels. "
        "When placing a new light, keep it realistic and only inside the red zone — no new architecture. "
        "Высокое презентационное качество: резкость, ночной контраст, без шума и артефактов. "
    )
    if saved_annotation is not None:
        if (markup_contract or "").strip():
            prompt += markup_contract.strip() + " "
        else:
            prompt += (
                "Image 2 is the SAME render with paint marks showing which luminaires to edit. "
                "RED = change marked fixtures only; CYAN = remove marked fixtures only. "
                "Unmarked fixtures must stay identical to Image 1. "
                "Do not keep paint in the final image. "
            )
        if guide_path is not None:
            prompt += (
                "Image 1 = clean render (copy all unmarked lights from here). "
                "Image 2 = marks over the same render. "
                "Output = Image 1 with ONLY marked luminaires edited. "
            )
    else:
        prompt += (
            "If a second image is provided with painted marks, treat marks only as a luminaire edit mask; "
            "do not keep paint in the final image; do not darken facade materials. "
        )
    prompt += f"Инструкция: {instruction.strip()}"
    prompt = append_facade_identity_lock(prompt)
    append_pipeline_log(base, "edit_start", {
        "instruction": instruction.strip(),
        "has_annotation": bool(saved_annotation),
        "has_markup_guide": bool(guide_path),
        "markup_colors": markup_colors,
        "markup_contract": bool((markup_contract or "").strip()),
        "input_images": [str(path) for path in images],
    })
    edited_path = base / "output" / "final_imported_render.png"
    meta = read_project_meta(base)
    model = router_model.strip() or (meta.get("routerai_model") or "")
    # Snapshot before AI overwrite so we can hard-lock unmarked pixels after the edit.
    original_backup = None
    if saved_annotation is not None and saved_annotation.exists():
        original_backup = base / "output" / "_edit_before.png"
        try:
            shutil.copy2(final_path, original_backup)
        except OSError:
            original_backup = None
    _, api_log = call_routerai(prompt, images, edited_path, project_base=base, model=model)
    append_pipeline_log(base, "routerai_edit", api_log)
    if original_backup is not None and original_backup.exists() and saved_annotation is not None:
        blend_mode = str((markup_colors or {}).get("mode") or "")
        if blend_mode == "change":
            try:
                from vision_agent.chat_agent import wants_place_fixture
                if wants_place_fixture(instruction):
                    blend_mode = "place"
            except Exception:
                pass
        blend_info = blend_edit_with_markup_mask(
            original_backup,
            edited_path,
            saved_annotation,
            mode=blend_mode,
        )
        append_pipeline_log(base, "edit_mask_blend", blend_info)
        try:
            original_backup.unlink(missing_ok=True)
        except Exception:
            pass
    apply_niteos_watermark(edited_path)
    render_audit = audit_render_coverage(base, edited_path, meta.get("last_placement_plan") or {})
    append_pipeline_log(base, "render_audit", render_audit)
    history_entry = save_render_history_entry(
        base,
        kind=(history_kind or "edit").strip() or "edit",
        note=instruction.strip(),
        prompt=instruction.strip(),
    )
    write_project_meta(base, {
        "status": "edited",
        "final": "output/final_imported_render.png",
        "last_history_entry": history_entry,
        "last_render_audit": render_audit,
        "feedback_required": True,
    })
    # Keep annotation snapshot next to history version when present.
    if saved_annotation and saved_annotation.exists() and history_entry:
        try:
            hist_file = str(history_entry.get("file") or "")
            stem = Path(hist_file).stem or f"edit_{history_entry.get('id')}"
            snap = base / "output" / "history" / f"{stem}_annotation.png"
            shutil.copy2(saved_annotation, snap)
            history_entry["annotation_file"] = f"history/{snap.name}"
            meta_now = read_project_meta(base)
            hist_list = list(meta_now.get("render_history") or [])
            for item in hist_list:
                if item.get("id") == history_entry.get("id"):
                    item["annotation_file"] = history_entry["annotation_file"]
                    break
            write_project_meta(base, {"render_history": hist_list, "last_history_entry": history_entry})
        except OSError:
            pass
    append_learning_event(base, "render_edited", payload={
        "instruction": instruction.strip(),
        "has_annotation": bool(saved_annotation),
        "markup_colors": markup_colors,
        "history_entry": history_entry,
        "render_audit": render_audit,
    })
    return edited_path


def _usage_date_key() -> str:
    return date.today().isoformat()


def _usage_file_path(date_key: str) -> Path:
    return USAGE_DIR / f"{date_key}.json"


def _valid_visitor_id(value: str | None) -> bool:
    return bool(value) and len(value) == 32 and all(c in "0123456789abcdef" for c in value.lower())


def _read_daily_usage(date_key: str) -> dict:
    path = _usage_file_path(date_key)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_daily_usage(date_key: str, data: dict) -> None:
    _usage_file_path(date_key).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_visitor_id(request: Request, response: Response) -> str:
    visitor_id = request.cookies.get(VISITOR_COOKIE)
    if _valid_visitor_id(visitor_id):
        return visitor_id
    visitor_id = uuid.uuid4().hex
    response.set_cookie(
        VISITOR_COOKIE,
        visitor_id,
        max_age=365 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return visitor_id


def render_count_today(visitor_id: str) -> int:
    with _usage_lock:
        data = _read_daily_usage(_usage_date_key())
        return int(data.get(visitor_id, {}).get("renders", 0))


def record_render(visitor_id: str) -> int:
    if not RENDER_LIMIT_ENABLED or not visitor_id:
        return 0
    with _usage_lock:
        date_key = _usage_date_key()
        data = _read_daily_usage(date_key)
        entry = data.get(visitor_id, {"renders": 0})
        entry["renders"] = int(entry.get("renders", 0)) + 1
        entry["last_at"] = now_iso()
        data[visitor_id] = entry
        _write_daily_usage(date_key, data)
        return int(entry["renders"])


def render_quota_exceeded_message() -> str:
    return (
        f"Лимит генераций на сегодня исчерпан ({DAILY_RENDER_LIMIT} в сутки). "
        f"Для детальной визуализации позвоните {CONTACT_PHONE}."
    )


def enforce_daily_render_quota(request: Request, response: Response) -> str:
    if not RENDER_LIMIT_ENABLED:
        return ""
    visitor_id = ensure_visitor_id(request, response)
    if render_count_today(visitor_id) >= DAILY_RENDER_LIMIT:
        raise HTTPException(status_code=429, detail=render_quota_exceeded_message())
    return visitor_id


def visitor_limit_status(request: Request, response: Response) -> dict:
    if not RENDER_LIMIT_ENABLED:
        return {"enabled": False}
    visitor_id = ensure_visitor_id(request, response)
    used = render_count_today(visitor_id)
    remaining = max(0, DAILY_RENDER_LIMIT - used)
    return {
        "enabled": True,
        "limit": DAILY_RENDER_LIMIT,
        "used": used,
        "remaining": remaining,
        "resets_on": (date.today() + timedelta(days=1)).isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
def landing() -> str:
    return inject_page_widgets(LANDING_HTML)


@app.get("/dealer", response_class=HTMLResponse)
def dealer_page() -> str:
    phone_tel = CONTACT_PHONE.replace(" ", "").replace("(", "").replace(")", "").replace("-", "")
    return inject_page_widgets(
        DEALER_HTML.replace("{{CONTACT_PHONE}}", CONTACT_PHONE)
        .replace("{{CONTACT_PHONE_TEL}}", phone_tel)
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> str:
    """Отдельное окно: истории сессий, рендеров и размещений."""
    return inject_page_widgets(ADMIN_HTML)


@app.get("/studio", response_class=HTMLResponse)
def studio_page() -> str:
    """Vision Agent Studio: анализ фасада → референс → генерация → чат."""
    return inject_page_widgets(AGENT_STUDIO_HTML)


# Клиентский режим временно отключён — см. CLIENT_HTML
# @app.get("/client", response_class=HTMLResponse)
# def client_page() -> str:
#     return CLIENT_HTML


@app.get("/client")
def client_page():
    return RedirectResponse(url="/dealer", status_code=302)


@app.get("/favicon.ico")
def favicon():
    icon = ROOT / "assets" / "niteos_icon.ico"
    if not icon.exists():
        raise HTTPException(status_code=404, detail="Favicon not found")
    return FileResponse(icon, media_type="image/x-icon")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "routerai_key_present": bool(routerai_key()),
        "routerai_model": routerai_model(),
    }


@app.get("/api/routerai-models")
def list_routerai_models() -> dict:
    try:
        from finetune.client import finetuned_endpoint_configured
        lora_ready = finetuned_endpoint_configured()
    except Exception:
        lora_ready = False
    models = []
    for item in ROUTERAI_IMAGE_MODELS:
        row = dict(item)
        if row.get("id") == FINETUNED_MODEL_ID:
            row["lora_endpoint"] = lora_ready
            row["mode"] = "lora_endpoint" if lora_ready else "soft_fewshot"
            row["label"] = (
                "NITEOS LoRA · дообученная (endpoint)"
                if lora_ready
                else "NITEOS LoRA · дообученная (few-shot, веса ещё не подключены)"
            )
        models.append(row)
    return {
        "models": models,
        "default": routerai_model(),
        "finetuned": {
            "id": FINETUNED_MODEL_ID,
            "endpoint_configured": lora_ready,
        },
    }


@app.get("/api/visitor/limits")
def visitor_limits(request: Request, response: Response) -> dict:
    return visitor_limit_status(request, response)


@app.post("/api/projects")
def create_project(request: Request, name: str = Form("New project"), mode: str = Form("dealer")) -> dict:
    project_id = uuid.uuid4().hex[:12]
    base = PROJECTS_DIR / project_id
    ensure_project_dirs(base)
    ip = log_ip_activity(action="project_created", request=request, project_id=project_id)
    write_project_meta(base, {
        "id": project_id,
        "name": name,
        "status": "created",
        "mode": mode if mode in {"dealer", "client"} else "dealer",
        "created_at": now_iso(),
        "created_from_ip": ip,
    })
    append_pipeline_log(base, "project_created", {"client_ip": ip, "name": name})
    return get_project(project_id)


@app.get("/api/client-products")
def list_client_products() -> dict:
    return {"products": [client_product_public(item) for item in CLIENT_PRODUCTS]}


@app.get("/api/client-products/{product_id}/preview")
def client_product_preview(product_id: str):
    product = client_product_by_id(product_id)
    path = export_front_path(product["export_id"])
    if not path:
        raise HTTPException(status_code=404, detail="Product preview not found")
    return FileResponse(path)


@app.get("/api/client-scenarios")
def list_client_scenarios() -> dict:
    scenarios = [client_scenario_public(item) for item in catalog_client_scenarios()]
    return {
        "scenarios": scenarios,
        "categories": [{
            "id": "catalog",
            "name": SCENARIO_CATEGORY_LABELS["catalog"],
            "scenarios": scenarios,
        }],
    }


@app.get("/api/client-scenarios/{scenario_id}/preview")
def client_scenario_preview(scenario_id: str):
    client_scenario_by_id(scenario_id)
    path = scenario_reference_path(scenario_id)
    if not path:
        raise HTTPException(status_code=404, detail="Scenario preview not found")
    return FileResponse(path)


@app.get("/api/client-templates")
def list_client_templates() -> dict:
    """Совместимость: отдаёт продукты и сценарии раздельно."""
    return {
        "products": [client_product_public(item) for item in CLIENT_PRODUCTS],
        "scenarios": [client_scenario_public(item) for item in catalog_client_scenarios()],
        "fixtures": [],
        "templates": [],
    }


@app.get("/api/client-templates/{template_id}/preview")
def client_template_preview(template_id: str):
    path = scenario_reference_path(template_id)
    if path:
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Preview not found")


def require_completed_feedback(base: Path) -> None:
    return


@app.post("/api/projects/{project_id}/client-render")
def client_render(
    request: Request,
    response: Response,
    project_id: str,
    scenario_id: str = Form(...),
    product_id: str = Form(""),
    prompt_override: str = Form(""),
    routerai_model: str = Form(""),
    review_profile: str = Form("economic"),
) -> dict:
    visitor_id = enforce_daily_render_quota(request, response)
    base = project_dir(project_id)
    require_completed_feedback(base)
    if not (base / "input" / "building.png").exists():
        raise HTTPException(status_code=400, detail="Сначала загрузите фото фасада")
    scenario = client_scenario_by_id(scenario_id)
    resolved_product_id = (product_id or "").strip() or product_id_for_scenario(scenario)
    apply_client_selection(base, resolved_product_id, scenario_id, prompt_override)
    model = resolve_routerai_model(routerai_model)
    write_project_meta(base, {"routerai_model": model})
    try:
        render_project(base, router_model=model, review_profile=review_profile)
    except Exception as e:
        append_pipeline_log(base, "render_error", {"error": str(e)})
        write_project_meta(base, {"status": "render_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    record_render(visitor_id)
    return get_project(project_id)


@app.get("/api/projects")
def list_projects() -> list[dict]:
    projects = []
    for path in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_dir():
            projects.append(project_summary(path))
    return projects


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    base = project_dir(project_id)
    meta = project_summary(base) | {"id": project_id}
    prompt_path = base / "prompt.txt"
    meta["prompt"] = prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else ""
    mode_path = base / "facade_mode.txt"
    meta["facade_mode"] = mode_path.read_text(encoding="utf-8", errors="ignore").strip() if mode_path.exists() else "auto"
    meta["mode"] = meta.get("mode") or "dealer"
    meta["dealer_scenario_id"] = meta.get("dealer_scenario_id") or ""
    meta["dealer_scenario_name"] = meta.get("dealer_scenario_name") or ""
    meta["dealer_product_id"] = meta.get("dealer_product_id") or ""
    meta["dealer_product_name"] = meta.get("dealer_product_name") or ""
    meta["dealer_legacy_ref"] = meta.get("dealer_legacy_ref") or ""
    meta["render_ies_files"] = meta.get("render_ies_files") or []
    meta["render_ies_items"] = meta.get("render_ies_items") or []
    if not meta["render_ies_items"] and meta["render_ies_files"]:
        meta["render_ies_items"] = build_render_ies_items(
            base,
            meta["render_ies_files"],
            meta.get("render_product_id") or meta.get("dealer_product_id") or "",
            meta.get("render_product_name") or meta.get("dealer_product_name") or "",
        )
    meta["render_ies_summary"] = meta.get("render_ies_summary") or ""
    meta["render_product_id"] = meta.get("render_product_id") or ""
    meta["render_product_name"] = meta.get("render_product_name") or ""
    meta["render_scenario_id"] = meta.get("render_scenario_id") or ""
    meta["render_scenario_name"] = meta.get("render_scenario_name") or ""
    meta["render_legacy_ref"] = meta.get("render_legacy_ref") or ""
    meta["routerai_model"] = meta.get("routerai_model") or routerai_model()
    meta["client_product_id"] = meta.get("client_product_id") or ""
    meta["client_product_name"] = meta.get("client_product_name") or ""
    meta["client_scenario_id"] = meta.get("client_scenario_id") or ""
    meta["client_scenario_name"] = meta.get("client_scenario_name") or ""
    meta["client_template_id"] = meta.get("client_template_id") or meta.get("client_scenario_id") or ""
    meta["client_template_name"] = meta.get("client_template_name") or meta.get("client_scenario_name") or ""
    meta["render_history"] = meta.get("render_history") or []
    meta["files"] = {
        "input": list_files(base / "input"),
        "ies": list_ies_files(base / "ies_library"),
        "references": list_files(base / "references"),
        "output": list_files(base / "output"),
        "latest": list_files(base / "project_export" / "latest"),
        "history": list_files(base / "output" / "history"),
    }
    return meta


@app.post("/api/projects/{project_id}/source")
async def upload_source(request: Request, project_id: str, file: UploadFile = File(...)) -> dict:
    base = project_dir(project_id)
    tmp = await save_upload(file, base / "input" / safe_name(file.filename or "source.png"))
    building = base / "input" / "building.png"
    try:
        save_rgb(tmp, building)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать изображение: {e}")
    mirror_to_library(building, "source")
    write_project_meta(base, {"status": "source_uploaded", "source_name": file.filename, "has_source": True})
    track_project_action(base, "upload_source", request, {"filename": file.filename, "saved_to_library": True})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/style")
async def upload_style(request: Request, project_id: str, file: UploadFile = File(...)) -> dict:
    base = project_dir(project_id)
    tmp = await save_upload(file, base / "references" / safe_name(file.filename or "style.png"))
    style = base / "references" / "style_reference_target.png"
    try:
        save_rgb(tmp, style)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать изображение: {e}")
    mirror_to_library(style, "style")
    write_project_meta(base, {"style_name": file.filename, "has_style": True})
    track_project_action(base, "upload_style", request, {"filename": file.filename, "saved_to_library": True})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/ies")
async def upload_ies(request: Request, project_id: str, files: list[UploadFile] = File(...)) -> dict:
    base = project_dir(project_id)
    ies_dir = base / "ies_library"
    ies_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        target = ies_dir / safe_name(upload.filename or "fixture.ies")
        await save_upload(upload, target)
        mirror_to_library(target, "ies")
        saved.append(target.name)
    write_project_meta(base, {"ies_count": len(list(ies_dir.glob("*.ies"))) + len(list(ies_dir.glob("*.IES")))})
    track_project_action(base, "upload_ies", request, {"files": saved, "saved_to_library": True})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/prompt")
def save_prompt(
    request: Request,
    project_id: str,
    prompt: str = Form(...),
    facade_mode: str = Form("auto"),
) -> dict:
    base = project_dir(project_id)
    (base / "prompt.txt").write_text(prompt.strip(), encoding="utf-8")
    (base / "facade_mode.txt").write_text(facade_mode.strip() or "auto", encoding="utf-8")
    write_project_meta(base, {"prompt_saved": True, "facade_mode": facade_mode})
    track_project_action(base, "save_prompt", request, {"facade_mode": facade_mode, "prompt_chars": len(prompt.strip())})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/enhance-prompt")
def enhance_prompt(project_id: str) -> dict:
    base = project_dir(project_id)
    prompt_path = base / "prompt.txt"
    raw = prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else ""
    enhanced = build_enhanced_task(raw)
    prompt_path.write_text(enhanced, encoding="utf-8")
    write_project_meta(base, {"prompt_saved": True})
    append_pipeline_log(base, "enhance_prompt", {"before": raw, "after": enhanced})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/package")
def package_project(project_id: str) -> dict:
    base = project_dir(project_id)
    prompt_path = base / "prompt.txt"
    user_prompt = prompt_path.read_text(encoding="utf-8", errors="ignore") if prompt_path.exists() else ""
    append_pipeline_log(base, "package_start", {
        "user_prompt": user_prompt,
        "facade_mode": (base / "facade_mode.txt").read_text(encoding="utf-8", errors="ignore").strip()
        if (base / "facade_mode.txt").exists() else "auto",
    })
    try:
        packager_log = run_packager(base)
        append_pipeline_log(base, "packager_done", packager_log)
        artifacts = collect_packager_artifacts(base)
        append_pipeline_log(base, "prompt_prepared", {
            "user_prompt": user_prompt,
            "chatgpt_prompt": artifacts.get("04_prompt_for_chatgpt.txt", ""),
            "gemini_prompt": artifacts.get("05_prompt_for_gemini_nano_banana.txt", ""),
            "ies_summary": artifacts.get("07_ies_summary.txt", ""),
            "equipment_draft": artifacts.get("08_equipment_draft.md", ""),
            "artifact_files": [item["name"] for item in artifacts.get("files", [])],
        })
    except Exception as e:
        append_pipeline_log(base, "package_error", {"error": str(e)})
        write_project_meta(base, {"status": "package_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    write_project_meta(base, {"status": "packaged"})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/dealer-scenario")
def set_dealer_scenario(
    request: Request,
    project_id: str,
    scenario_id: str = Form(...),
    product_id: str = Form(""),
) -> dict:
    base = project_dir(project_id)
    apply_dealer_scenario(base, scenario_id, product_id)
    track_project_action(base, "dealer_scenario_selected", request, {"scenario_id": scenario_id, "product_id": product_id})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/dealer-style-ref")
def set_dealer_style_ref(project_id: str, scenario_id: str = Form(...)) -> dict:
    scenario = client_scenario_by_id(scenario_id)
    ref = scenario_reference_path(scenario_id)
    if not ref:
        raise HTTPException(status_code=404, detail=f"Референс не найден: {scenario_id}")
    base = project_dir(project_id)
    save_rgb(ref, base / "references" / "style_reference_target.png")
    write_project_meta(base, {"style_name": ref.name, "has_style": True, "status": "style_ref_applied"})
    append_pipeline_log(base, "dealer_style_ref_applied", {
        "scenario_id": scenario_id,
        "scenario_name": scenario.get("name"),
        "style_name": ref.name,
    })
    return get_project(project_id)


@app.post("/api/projects/{project_id}/dealer-legacy-template")
def apply_dealer_legacy_template(
    request: Request,
    project_id: str,
    library_path: str = Form(...),
    name: str = Form(""),
    template_id: str = Form(""),
) -> dict:
    base = project_dir(project_id)
    # Legacy-шаблон: эталон + привязанные IES (если есть), чтобы фотометрия переносилась в проект.
    ies_dir = base / "ies_library"
    if ies_dir.exists():
        for old in ies_dir.glob("*.ies"):
            old.unlink()
        for old in ies_dir.glob("*.IES"):
            old.unlink()
    product_front = base / "references" / "product_front.png"
    if product_front.exists():
        product_front.unlink()
    src = resolve_library_file("style", library_path)
    copied = copy_unique(src, base / "references", src.name)
    save_rgb(copied, base / "references" / "style_reference_target.png")
    label = (name or src.name).strip()
    legacy_id = (template_id or "").strip()
    if not legacy_id:
        digits = re.sub(r"\D+", "", label)
        legacy_id = f"legacy_{digits}" if digits else ""
    binding = DEALER_LEGACY_TEMPLATE_BINDINGS.get(legacy_id) or {}
    product = None
    if binding.get("product_id"):
        try:
            product = client_product_by_id(binding["product_id"])
        except HTTPException:
            product = None
    saved_ies: list[str] = []
    for filename in (binding.get("ies_files") or []):
        src_ies = resolve_ies_source(filename)
        if not src_ies:
            continue
        target = copy_ies_with_photo(src_ies, ies_dir)
        saved_ies.append(target.name)
    if product:
        front = export_front_path(product.get("export_id") or "")
        if front:
            save_rgb(front, base / "references" / "product_front.png")
    # Обновим prompt, чтобы при шаблоне сохранялась логика переноса схемы
    (base / "prompt.txt").write_text(build_dealer_legacy_template_prompt(label, product, base), encoding="utf-8")
    if product and product.get("facade_mode"):
        (base / "facade_mode.txt").write_text(product.get("facade_mode") or "classic", encoding="utf-8")
    write_project_meta(base, {
        "style_name": src.name,
        "has_style": True,
        "dealer_legacy_ref": label,
        "dealer_scenario_id": "",
        "dealer_scenario_name": "",
        "dealer_product_id": (product or {}).get("id") or "",
        "dealer_product_name": (product or {}).get("name") or "",
        "render_product_id": "",
        "render_product_name": "",
        "render_scenario_id": "",
        "render_scenario_name": "",
        "render_legacy_ref": "",
        "render_ies_files": [],
        "render_ies_items": [],
        "render_ies_summary": "",
        "ies_count": len(saved_ies),
        "status": "legacy_template_applied",
    })
    append_pipeline_log(base, "dealer_legacy_template_applied", {
        "library_path": library_path,
        "name": label,
        "product": (product or {}).get("name") or "",
        "ies_files": saved_ies,
    })
    track_project_action(
        base,
        "dealer_legacy_template_selected",
        request,
        {"filename": label, "product_id": (product or {}).get("id") or ""},
    )
    return get_project(project_id)


@app.post("/api/projects/{project_id}/agent-preview")
def agent_preview(
    project_id: str,
    prompt: str = Form(""),
    facade_mode: str = Form(""),
    routerai_model: str = Form(""),
) -> dict:
    base = project_dir(project_id)
    try:
        preview = prepare_agent_render_prompt(
            base,
            prompt_override=prompt,
            facade_mode_override=facade_mode,
            router_model=routerai_model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "ok": True,
        "project_id": project_id,
        "facade_mode": preview["facade_mode"],
        "routerai_model": preview["routerai_model"],
        "prompt_chars": preview["prompt_chars"],
        "base_prompt": preview["base_prompt"],
        "render_prompt": preview["render_prompt"],
        "placement_plan": preview["placement_plan"],
        "placement_candidates": [
            {
                "candidate_id": item.get("candidate_id", ""),
                "strategy": item.get("strategy", ""),
                "family": item.get("family", ""),
                "score": item.get("score", {}),
                "strategy_memory": item.get("strategy_memory", {}),
            }
            for item in preview["placement_candidates"]
        ],
        "learning_guidance": preview["learning_guidance"],
    }


def build_auto_viz_response(project_id: str, result: dict) -> dict:
    classification = result.get("classification") or {}
    preview = result.get("preview") or {}
    applied = result.get("applied") or {}
    fname = str(classification.get("filename") or applied.get("filename") or "").strip()
    project = get_project(project_id)
    return {
        "ok": True,
        "project_id": project_id,
        "classification": classification,
        "scenario_id": "",
        "scenario_name": f"Авто-эталон: {fname}" if fname else "Авто-эталон виз",
        "viz_filename": fname,
        "product_name": "MAGISTRAL",
        "confidence": classification.get("confidence"),
        "reason": classification.get("reason") or "",
        "fallback": bool(classification.get("fallback") or (result.get("api_log") or {}).get("fallback")),
        "base_prompt": preview.get("base_prompt") or project.get("prompt") or "",
        "render_prompt": preview.get("render_prompt") or "",
        "prompt_chars": preview.get("prompt_chars") or 0,
        "placement_plan": preview.get("placement_plan") or {},
        "placement_candidates": [
            {
                "candidate_id": item.get("candidate_id", ""),
                "strategy": item.get("strategy", ""),
                "family": item.get("family", ""),
                "score": item.get("score", {}),
            }
            for item in (preview.get("placement_candidates") or [])
        ],
        "learning_guidance": preview.get("learning_guidance") or {},
        "routerai_model": preview.get("routerai_model") or "",
        "generated": bool(result.get("generated")),
        "final": result.get("final") or "",
        "project": project,
    }


@app.post("/api/projects/{project_id}/auto-scenario")
def auto_scenario(
    request: Request,
    response: Response,
    project_id: str,
    routerai_model: str = Form(""),
    classifier_model: str = Form(""),
    generate: str = Form("1"),
    viz_filename: str = Form(""),
    apply: str = Form("1"),
) -> dict:
    """Авто: выбрать эталон из 20 виз и сразу сгенерировать финал (source + style ref)."""
    base = project_dir(project_id)
    source = base / "input" / "building.png"
    if not source.exists():
        raise HTTPException(status_code=400, detail="Сначала загрузите фото фасада")
    should_generate = str(generate or apply or "1").strip().lower() not in {"0", "false", "no"}
    visitor_id = ""
    if should_generate:
        require_completed_feedback(base)
        visitor_id = enforce_daily_render_quota(request, response)
    try:
        result = run_auto_viz_pipeline(
            base,
            router_model=routerai_model,
            classifier_model=classifier_model,
            viz_filename=viz_filename,
            generate=should_generate,
        )
    except Exception as e:
        track_project_action(base, "auto_viz_error", request, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    if should_generate and result.get("generated") and visitor_id:
        record_render(visitor_id)
    classification = result.get("classification") or {}
    track_project_action(base, "auto_viz_done", request, {
        "viz_filename": classification.get("filename") or "",
        "confidence": classification.get("confidence"),
        "fallback": bool(classification.get("fallback")),
        "generated": bool(result.get("generated")),
    })
    return build_auto_viz_response(project_id, result)


@app.get("/api/auto-test-photos")
def auto_test_photos() -> dict:
    """Каталог 20 эталонов ночной подсветки (assets/viz_examples) для авто-режима."""
    items = list_auto_test_photos()
    return {"ok": True, "count": len(items), "items": items}


@app.get("/api/auto-test-photos/{filename}")
def auto_test_photo_file(filename: str):
    safe = Path(filename).name
    path = VIZ_EXAMPLES_DIR / safe
    if not path.exists() or path.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(status_code=404, detail="Test photo not found")
    return FileResponse(path)


@app.get("/api/auto-test-photos/{filename}/thumb")
def auto_test_photo_thumb(filename: str):
    safe = Path(filename).name
    stem = Path(safe).stem
    thumb = VIZ_THUMBS_DIR / f"{stem}.jpg"
    if not thumb.exists():
        list_auto_test_photos()
    if not thumb.exists():
        path = VIZ_EXAMPLES_DIR / safe
        if not path.exists():
            raise HTTPException(status_code=404, detail="Test thumb not found")
        return FileResponse(path)
    return FileResponse(thumb)


@app.post("/api/projects/{project_id}/auto-test-load")
def auto_test_load(
    request: Request,
    response: Response,
    project_id: str,
    filename: str = Form(...),
    run_auto: str = Form("1"),
    generate: str = Form("1"),
    routerai_model: str = Form(""),
    classifier_model: str = Form(""),
) -> dict:
    """Взять выбранный эталон виз как style ref и сразу сгенерировать финал (не подменяет source)."""
    base = project_dir(project_id)
    source = base / "input" / "building.png"
    if not source.exists():
        raise HTTPException(status_code=400, detail="Сначала загрузите своё фото фасада в шаге 1")
    should_run = str(run_auto or "1").strip().lower() not in {"0", "false", "no"}
    should_generate = str(generate or "1").strip().lower() not in {"0", "false", "no"}
    auto_result = None
    if should_run:
        visitor_id = ""
        if should_generate:
            require_completed_feedback(base)
            visitor_id = enforce_daily_render_quota(request, response)
        try:
            result = run_auto_viz_pipeline(
                base,
                router_model=routerai_model,
                classifier_model=classifier_model,
                viz_filename=filename,
                generate=should_generate,
            )
            if should_generate and result.get("generated") and visitor_id:
                record_render(visitor_id)
            track_project_action(base, "auto_viz_manual_pick", request, {
                "filename": Path(filename).name,
                "generated": bool(result.get("generated")),
            })
            auto_result = build_auto_viz_response(project_id, result)
        except HTTPException:
            raise
        except Exception as e:
            track_project_action(base, "auto_viz_error", request, {"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    project = get_project(project_id)
    return {"ok": True, "project": project, "auto": auto_result}


def _studio_deps():
    import cloud_app as mod
    return make_studio_deps_from_cloud(mod)


@app.get("/api/studio/references")
def studio_references_catalog() -> dict:
    return {"ok": True, "items": list_references_public()}


@app.get("/api/studio/references/{ref_id}/file")
def studio_reference_file(ref_id: str):
    item = get_reference_by_id(ref_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reference not found")
    path = reference_path(item)
    if not path:
        raise HTTPException(status_code=404, detail="Reference file missing")
    return FileResponse(path)


@app.get("/api/studio/references/{ref_id}/thumb")
def studio_reference_thumb(ref_id: str):
    item = get_reference_by_id(ref_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reference not found")
    thumb_name = str(item.get("thumb") or "")
    thumb = THUMBS_DIR / thumb_name if thumb_name else None
    if thumb and thumb.exists():
        return FileResponse(thumb, media_type="image/jpeg")
    path = reference_path(item)
    if not path:
        raise HTTPException(status_code=404, detail="Reference file missing")
    return FileResponse(path)


@app.get("/api/projects/{project_id}/studio/state")
def studio_state(project_id: str) -> dict:
    base = project_dir(project_id)
    return get_studio_state(base)


@app.post("/api/projects/{project_id}/studio/restore-history")
def studio_restore_history(
    request: Request,
    project_id: str,
    history_id: str = Form(...),
) -> dict:
    """Make a history version the active final for further brush/chat edits."""
    base = project_dir(project_id)
    try:
        result = restore_studio_history(base, history_id)
    except Exception as e:
        track_project_action(base, "studio_restore_error", request, {"error": str(e), "history_id": history_id})
        raise HTTPException(status_code=400, detail=str(e)) from e
    track_project_action(base, "studio_restore_history", request, {"history_id": history_id})
    payload = get_studio_state(base)
    payload["restored_id"] = result.get("restored_id")
    payload["message"] = result.get("message") or ""
    return payload


@app.post("/api/projects/{project_id}/studio/set-final")
async def studio_set_final(
    request: Request,
    project_id: str,
    file: UploadFile = File(...),
    note: str = Form(""),
) -> dict:
    """Set pasted/copied image as the active working final for further edits."""
    base = project_dir(project_id)
    ensure_project_dirs(base)
    tmp = await save_upload(file, base / "output" / safe_name(file.filename or "pasted_final.png"))
    try:
        building_like = base / "output" / "_pasted_norm.png"
        save_rgb(tmp, building_like)
        result = set_studio_final_from_image(
            base,
            _studio_deps(),
            building_like,
            note=note or f"paste:{file.filename or 'image'}",
        )
    except Exception as e:
        track_project_action(base, "studio_set_final_error", request, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            (base / "output" / "_pasted_norm.png").unlink(missing_ok=True)
        except Exception:
            pass
    track_project_action(base, "studio_set_final", request, {"filename": file.filename})
    payload = get_studio_state(base)
    payload["history_entry"] = result.get("history_entry")
    payload["message"] = "Working image updated from copy/paste"
    return payload


@app.post("/api/projects/{project_id}/studio/start")
def studio_start(
    request: Request,
    response: Response,
    project_id: str,
    routerai_model: str = Form(""),
) -> dict:
    visitor_id = enforce_daily_render_quota(request, response)
    base = project_dir(project_id)
    track_project_action(base, "studio_start", request, {"visitor_id": visitor_id})
    try:
        result = run_studio_start(base, _studio_deps(), router_model=routerai_model)
    except Exception as e:
        track_project_action(base, "studio_start_error", request, {"error": str(e)})
        write_project_meta(base, {"status": "studio_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    track_project_action(base, "studio_start_ok", request, {"scheme": (result.get("state") or {}).get("scheme")})
    payload = get_studio_state(base)
    payload["explanation"] = result.get("explanation") or ""
    return payload


@app.post("/api/projects/{project_id}/studio/chat")
async def studio_chat(
    request: Request,
    response: Response,
    project_id: str,
    message: str = Form(""),
    routerai_model: str = Form(""),
    annotation: str = Form(""),
    annotation_file: UploadFile | None = File(None),
) -> dict:
    visitor_id = enforce_daily_render_quota(request, response)
    base = project_dir(project_id)
    has_ann = bool(annotation) or (annotation_file is not None and bool(getattr(annotation_file, "filename", None)))
    track_project_action(base, "studio_chat", request, {
        "visitor_id": visitor_id,
        "message": (message or "")[:200],
        "has_annotation": has_ann,
    })
    try:
        result = run_studio_chat(
            base,
            _studio_deps(),
            message,
            router_model=routerai_model,
            annotation_data_url=annotation or None,
            annotation_upload=annotation_file,
        )
    except Exception as e:
        track_project_action(base, "studio_chat_error", request, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e
    payload = get_studio_state(base)
    payload["reply"] = result.get("reply") or ""
    payload["intent"] = result.get("intent") or {}
    payload["has_markup"] = bool(result.get("has_markup"))
    return payload


@app.post("/api/projects/{project_id}/render")
def auto_render(
    request: Request,
    response: Response,
    project_id: str,
    prompt: str = Form(""),
    facade_mode: str = Form(""),
    routerai_model: str = Form(""),
    review_profile: str = Form("economic"),
) -> dict:
    visitor_id = enforce_daily_render_quota(request, response)
    base = project_dir(project_id)
    require_completed_feedback(base)
    if prompt.strip():
        (base / "prompt.txt").write_text(prompt.strip(), encoding="utf-8")
        write_project_meta(base, {"prompt_saved": True})
    if facade_mode.strip():
        (base / "facade_mode.txt").write_text(facade_mode.strip(), encoding="utf-8")
    model = resolve_routerai_model(routerai_model)
    write_project_meta(base, {"routerai_model": model})
    track_project_action(base, "render_request", request, {"routerai_model": model, "review_profile": review_profile})
    try:
        render_project(base, router_model=model, review_profile=review_profile)
    except Exception as e:
        track_project_action(base, "render_error", request, {"error": str(e)})
        write_project_meta(base, {"status": "render_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    record_render(visitor_id)
    track_project_action(base, "render_done", request, {"status": "rendered"})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/edit")
async def edit_render(
    request: Request,
    project_id: str,
    instruction: str = Form(...),
    annotation: str = Form(""),
    annotation_file: UploadFile | None = File(None),
) -> dict:
    base = project_dir(project_id)
    has_ann = bool(annotation) or (annotation_file is not None and bool(getattr(annotation_file, "filename", None)))
    track_project_action(base, "edit_request", request, {"has_annotation": has_ann})
    try:
        edit_project_render(
            base,
            instruction,
            annotation_data_url=annotation or None,
            annotation_upload=annotation_file,
        )
    except Exception as e:
        track_project_action(base, "edit_error", request, {"error": str(e)})
        write_project_meta(base, {"status": "edit_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    track_project_action(base, "edit_done", request, {"status": "edited"})
    return get_project(project_id)


@app.post("/api/projects/{project_id}/feedback")
def submit_project_feedback(
    request: Request,
    project_id: str,
    vote: str = Form(""),
    rating: int = Form(0),
    issue_type: str = Form(""),
    comment: str = Form(""),
    contact: str = Form(""),
) -> dict:
    base = project_dir(project_id)
    meta = read_project_meta(base)
    safe_vote = normalize_feedback_vote(vote)
    if not safe_vote and rating in (1, 5):
        # Backward compatible: 5→like, 1→dislike
        safe_vote = "like" if int(rating) >= 4 else "dislike"
    if not safe_vote:
        raise HTTPException(status_code=400, detail="Выберите: нравится или не нравится")
    safe_rating = rating_from_vote(safe_vote) if safe_vote else max(0, min(5, int(rating or 0)))
    safe_issue_type = normalize_feedback_issue_type(issue_type)
    history_entry = meta.get("last_history_entry") or {}
    placement_plan = meta.get("last_placement_plan") or {}
    ip = client_ip_from_request(request)
    prompt_used = ""
    hist_id = history_entry.get("id")
    for item in list(meta.get("render_history") or []):
        if str(item.get("id")) == str(hist_id):
            prompt_used = item.get("prompt") or ""
            break
    if not prompt_used:
        prompt_path = base / "prompt.txt"
        if prompt_path.exists():
            prompt_used = prompt_path.read_text(encoding="utf-8", errors="ignore")
    entry = {
        "project_id": project_id,
        "vote": safe_vote,
        "rating": safe_rating,
        "issue_type": safe_issue_type,
        "issue_label": FEEDBACK_ISSUE_LABELS.get(safe_issue_type, ""),
        "comment": (comment or "").strip()[:4000],
        "contact": (contact or "").strip()[:200],
        "prompt": (prompt_used or "")[:12000],
        "scenario_id": meta.get("dealer_scenario_id") or meta.get("render_scenario_id") or "",
        "scenario_name": meta.get("dealer_scenario_name") or meta.get("render_scenario_name") or "",
        "render_history_id": history_entry.get("id"),
        "placement_strategy": placement_plan.get("strategy") or placement_plan.get("candidate_id") or "",
        "placement_family": placement_plan.get("family") or "",
        "work_mode": meta.get("work_mode") or "",
        "auto_viz_ref": meta.get("auto_viz_ref") or "",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "client_ip": ip,
    }
    fname = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{project_id[:8]}_{uuid.uuid4().hex[:6]}.json"
    (FEEDBACK_DIR / fname).write_text(
        json.dumps(entry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    learning_event = append_learning_event(
        base,
        "feedback_submitted",
        rating=safe_rating,
        vote=safe_vote,
        payload={
            "feedback_file": fname,
            "vote": safe_vote,
            "rating": safe_rating,
            "issue_type": safe_issue_type,
            "issue_label": FEEDBACK_ISSUE_LABELS.get(safe_issue_type, ""),
            "comment": entry["comment"],
            "contact": entry["contact"],
            "render_history_id": history_entry.get("id"),
            "placement_strategy": entry["placement_strategy"],
            "placement_family": entry["placement_family"],
            "automatic_review": meta.get("automatic_review") or {},
            "has_contact": bool(entry["contact"]),
        },
    )
    attach_feedback_to_history_entry(
        base,
        history_id=history_entry.get("id"),
        vote=safe_vote,
        comment=entry["comment"],
        contact=entry["contact"],
        issue_type=safe_issue_type,
    )
    write_project_meta(base, {"feedback_required": False, "last_feedback_at": now_iso(), "last_feedback_vote": safe_vote})
    append_pipeline_log(base, "feedback_submitted", {
        "vote": safe_vote,
        "rating": safe_rating,
        "issue_type": safe_issue_type,
        "comment": entry["comment"][:300],
        "has_contact": bool(entry["contact"]),
        "file": fname,
        "client_ip": ip,
        "render_history_id": history_entry.get("id"),
    })
    log_ip_activity(action="feedback_submitted", request=request, project_id=project_id, detail={
        "vote": safe_vote,
        "rating": safe_rating,
        "issue_type": safe_issue_type,
        "has_comment": bool(entry["comment"]),
        "has_contact": bool(entry["contact"]),
    })
    return {"ok": True, "learning_event_id": learning_event["event_id"], "vote": safe_vote}


@app.get("/api/admin/learning-summary")
def admin_learning_summary(password: str = "", limit: int = 20) -> dict:
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    return learning_events_summary(limit)


@app.get("/api/admin/finetune-dataset")
def admin_finetune_dataset(password: str = "") -> dict:
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        from finetune.client import finetuned_endpoint_configured
        from finetune.stats import get_finetune_dataset_stats
        stats = get_finetune_dataset_stats()
        stats["endpoint_configured"] = finetuned_endpoint_configured()
        stats["lora_id"] = os.getenv("FINETUNED_LORA_ID", "niteos_archlight_v1")
        stats["model_id"] = FINETUNED_MODEL_ID
        return {"ok": True, **stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/finetune-dataset/rebuild")
def admin_finetune_dataset_rebuild(password: str = Form("")) -> dict:
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        from finetune.export_dataset import export_dataset
        summary = export_dataset(
            cloud_dir=CLOUD_DIR,
            include_fixtures=True,
            include_viz=True,
            include_web=True,
            download_web=False,
            strip_wm=True,
        )
        return {"ok": True, "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _admin_project_card(base: Path) -> dict:
    meta = read_project_meta(base)
    source = base / "input" / "building.png"
    final = base / "output" / "final_imported_render.png"
    style = base / "references" / "style_reference_target.png"
    plan = meta.get("last_placement_plan") or {}
    auto_viz = meta.get("auto_viz") or {}
    history = list(meta.get("render_history") or [])
    return {
        "project_id": base.name,
        "project_name": meta.get("name") or base.name,
        "status": meta.get("status") or "",
        "updated_at": meta.get("updated_at") or "",
        "work_mode": meta.get("work_mode") or "",
        "scenario_name": meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or "",
        "auto_viz_ref": meta.get("auto_viz_ref") or (auto_viz.get("filename") if isinstance(auto_viz, dict) else "") or "",
        "auto_reason": (auto_viz.get("reason") if isinstance(auto_viz, dict) else "") or "",
        "placement_family": plan.get("family") or "",
        "placement_strategy": plan.get("strategy") or "",
        "routerai_model": meta.get("routerai_model") or "",
        "last_feedback_vote": meta.get("last_feedback_vote") or "",
        "last_feedback_comment": meta.get("last_feedback_comment") or "",
        "last_feedback_contact": meta.get("last_feedback_contact") or "",
        "render_history_count": len(history),
        "has_source": source.exists(),
        "has_final": final.exists(),
        "has_style": style.exists(),
        "source_url": f"/api/projects/{base.name}/file/input/building.png" if source.exists() else "",
        "final_url": f"/api/projects/{base.name}/file/output/final_imported_render.png" if final.exists() else "",
        "style_url": f"/api/projects/{base.name}/file/references/style_reference_target.png" if style.exists() else "",
        "dealer_url": f"/dealer?project={base.name}",
    }


@app.get("/api/admin/sessions")
def admin_sessions(password: str = "", limit: int = 50) -> dict:
    """Список проектов/сессий с превью source/final для админ-окна."""
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    limit = max(1, min(int(limit or 50), 200))
    projects = sorted(PROJECTS_DIR.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    items = [_admin_project_card(base) for base in projects if base.is_dir()][:limit]
    return {"ok": True, "count": len(items), "items": items}


@app.get("/api/admin/render-history")
def admin_render_history(password: str = "", limit: int = 100) -> dict:
    """Сводка истории генераций по всем проектам для админ-проверки со временем."""
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    limit = max(1, min(int(limit or 100), 500))
    items: list[dict] = []
    projects = sorted(PROJECTS_DIR.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for base in projects:
        if not base.is_dir():
            continue
        meta = read_project_meta(base)
        plan = meta.get("last_placement_plan") or {}
        auto_viz = meta.get("auto_viz") or {}
        source = base / "input" / "building.png"
        history = list(meta.get("render_history") or [])
        for entry in reversed(history):
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("file") or "")
            file_path = (base / "output" / rel) if rel else None
            items.append({
                "project_id": base.name,
                "project_name": meta.get("name") or base.name,
                "history_id": entry.get("id"),
                "kind": entry.get("kind") or "",
                "created_at": entry.get("created_at") or "",
                "work_mode": entry.get("work_mode") or meta.get("work_mode") or "",
                "scenario_name": entry.get("scenario_name") or meta.get("render_scenario_name") or meta.get("dealer_scenario_name") or "",
                "auto_viz_ref": entry.get("auto_viz_ref") or meta.get("auto_viz_ref") or (auto_viz.get("filename") if isinstance(auto_viz, dict) else "") or "",
                "placement_family": entry.get("placement_family") or plan.get("family") or "",
                "placement_strategy": entry.get("placement_strategy") or plan.get("strategy") or "",
                "routerai_model": entry.get("routerai_model") or meta.get("routerai_model") or "",
                "note": (entry.get("note") or "")[:240],
                "prompt": entry.get("prompt") or "",
                "prompt_preview": ((entry.get("prompt") or entry.get("note") or "")[:350]),
                "prompt_file": entry.get("prompt_file") or "",
                "prompt_url": (
                    f"/api/projects/{base.name}/file/output/{entry.get('prompt_file')}"
                    if entry.get("prompt_file") else ""
                ),
                "feedback_vote": entry.get("feedback_vote") or "",
                "feedback_comment": entry.get("feedback_comment") or "",
                "feedback_contact": entry.get("feedback_contact") or "",
                "feedback_issue_type": entry.get("feedback_issue_type") or "",
                "feedback_at": entry.get("feedback_at") or "",
                "feedback_status": entry.get("feedback_status") or ("submitted" if entry.get("feedback_vote") else "pending"),
                "generation_archive": entry.get("generation_archive") or "",
                "product_name": entry.get("product_name") or meta.get("render_product_name") or "",
                "ies_names": entry.get("ies_names") or [],
                "facade_mode": entry.get("facade_mode") or "",
                "file": rel,
                "exists": bool(file_path and file_path.exists()),
                "url": f"/api/projects/{base.name}/file/output/{rel}" if rel else "",
                "source_url": f"/api/projects/{base.name}/file/input/building.png" if source.exists() else "",
                "last_feedback_vote": entry.get("feedback_vote") or meta.get("last_feedback_vote") or "",
                "dealer_url": f"/dealer?project={base.name}",
            })
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break
    feedback_count = len(list(FEEDBACK_DIR.glob("*.json"))) if FEEDBACK_DIR.exists() else 0
    generations_count = len(list(GENERATIONS_DIR.glob("*.json"))) if GENERATIONS_DIR.exists() else 0
    learning_count = 0
    if LEARNING_EVENTS_PATH.exists():
        learning_count = sum(1 for line in LEARNING_EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    return {
        "count": len(items),
        "feedback_files": feedback_count,
        "generation_archives": generations_count,
        "learning_events": learning_count,
        "learning_events_path": "cloud_data/learning/events.jsonl",
        "feedback_dir": "cloud_data/feedback/",
        "generations_dir": "cloud_data/generations/",
        "per_project_history_dir": "cloud_data/projects/<id>/output/history/",
        "items": items,
    }


@app.get("/api/admin/learned-rules")
def admin_learned_rules(password: str = "", limit: int = 1000) -> dict:
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    return learned_rules_summary(limit)


@app.get("/api/admin/ip-activity")
def admin_ip_activity(
    password: str = "",
    day: str = "",
    ip: str = "",
    limit: int = 200,
) -> dict:
    """Журнал действий по IP. Пароль: CATALOG_ADMIN_PASSWORD (если задан)."""
    if CATALOG_ADMIN_PASSWORD and password != CATALOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    day_key = (day or date.today().isoformat()).strip()
    path = IP_ACTIVITY_DIR / f"{day_key}.jsonl"
    entries: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ip and str(item.get("ip") or "") != ip:
                continue
            entries.append(item)
    entries = entries[-max(1, min(limit, 2000)):]
    by_ip: dict[str, int] = {}
    for item in entries:
        key = str(item.get("ip") or "unknown")
        by_ip[key] = by_ip.get(key, 0) + 1
    return {
        "day": day_key,
        "count": len(entries),
        "by_ip": dict(sorted(by_ip.items(), key=lambda kv: (-kv[1], kv[0]))),
        "entries": entries,
        "files": sorted(p.name for p in IP_ACTIVITY_DIR.glob("*.jsonl")),
    }


@app.get("/api/projects/{project_id}/pipeline-log")
def get_pipeline_log(project_id: str) -> dict:
    base = project_dir(project_id)
    return {"project_id": project_id, "entries": read_pipeline_log(base)}


@app.get("/api/projects/{project_id}/pipeline-log/download")
def download_pipeline_log(project_id: str):
    base = project_dir(project_id)
    path = pipeline_log_path(base)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Pipeline log not found")
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"pipeline-{project_id}.jsonl",
    )


@app.get("/api/projects/{project_id}/download.zip")
def download_project_zip(project_id: str):
    base = project_dir(project_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(base.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(base).as_posix())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="niteos-{project_id}.zip"'},
    )


@app.get("/api/projects/{project_id}/file/{kind}/{file_path:path}")
def get_project_file(project_id: str, kind: Literal["input", "ies", "references", "output", "latest", "history"], file_path: str):
    base = project_dir(project_id)
    roots = {
        "input": base / "input",
        "ies": base / "ies_library",
        "references": base / "references",
        "output": base / "output",
        "latest": base / "project_export" / "latest",
        "history": base / "output" / "history",
    }
    root = roots[kind].resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)


@app.post("/api/library/{kind}")
async def upload_library_file(kind: Literal["source", "ies", "style"], file: UploadFile = File(...)) -> dict:
    target = library_root(kind) / safe_name(file.filename or "file")
    await save_upload(file, target)
    return {"ok": True, "kind": kind, "file": target.name}


@app.get("/api/dealer-legacy-style-refs")
def list_dealer_legacy_style_refs() -> dict:
    ensure_legacy_style_refs()
    refs = []
    for index, name in enumerate(DEALER_LEGACY_STYLE_FILES, start=1):
        path = STYLE_LIBRARY_DIR / name
        legacy_id = f"legacy_{index}"
        binding = DEALER_LEGACY_TEMPLATE_BINDINGS.get(legacy_id) or {}
        product = None
        if binding.get("product_id"):
            try:
                product = client_product_by_id(binding["product_id"])
            except HTTPException:
                product = None
        refs.append({
            "id": legacy_id,
            "name": f"Шаблон {index}",
            "library_path": name,
            "has_preview": path.exists(),
            "product_id": (product or {}).get("id") or "",
            "product_name": (product or {}).get("name") or "",
            "ies_files": binding.get("ies_files") or [],
            "prompt_updated": False,
        })
    return {"refs": refs}


@app.get("/api/library")
def library() -> dict:
    return {
        "source": list_files(SOURCE_LIBRARY_DIR, IMAGE_EXTS),
        "ies": list_ies_files(IES_LIBRARY_DIR),
        "style": list_files(STYLE_LIBRARY_DIR, IMAGE_EXTS),
    }


@app.get("/api/library/ies/photo/{file_path:path}")
def library_ies_photo(file_path: str):
    ies = resolve_library_file("ies", file_path)
    photo = ies_catalog_photo(ies)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(photo)


@app.get("/api/projects/{project_id}/ies-photo/{file_path:path}")
def project_ies_photo(project_id: str, file_path: str):
    base = project_dir(project_id)
    root = (base / "ies_library").resolve()
    ies = (root / file_path).resolve()
    if not str(ies).startswith(str(root)) or not ies.exists():
        raise HTTPException(status_code=404, detail="IES not found")
    photo = ies_catalog_photo(ies)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(photo)


@app.post("/api/admin/library/ies")
async def admin_add_library_ies(
    password: str = Form(...),
    ies: UploadFile = File(...),
    photo: UploadFile | None = File(None),
) -> dict:
    _require_catalog_password(password)
    if (Path(ies.filename or "").suffix or "").lower() != ".ies":
        raise HTTPException(status_code=400, detail="Нужен файл с расширением .ies")
    target = IES_LIBRARY_DIR / safe_name(ies.filename or "fixture.ies")
    await save_upload(ies, target)
    saved_photo = ""
    if photo and photo.filename:
        ext = (Path(photo.filename).suffix or ".jpg").lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        photo_target = target.with_suffix(ext)
        await save_upload(photo, photo_target)
        saved_photo = photo_target.name
    return {"ok": True, "ies": target.name, "photo": saved_photo}


@app.delete("/api/admin/library/ies")
def admin_delete_library_ies(password: str = Form(...), relative_path: str = Form(...)) -> dict:
    _require_catalog_password(password)
    ies = resolve_library_file("ies", relative_path)
    photo = ies_photo_path(ies)
    ies.unlink(missing_ok=True)
    if photo:
        photo.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/fixtures")
def fixtures_catalog() -> dict:
    return {"fixtures": list_fixtures()}


@app.get("/api/fixtures/{fixture_id}/photo")
def fixture_photo(fixture_id: str):
    folder = _fixture_dir_by_id(fixture_id)
    if not str(folder).startswith(str(FIXTURES_LIBRARY_DIR.resolve())) or not folder.exists():
        raise HTTPException(status_code=404, detail="Fixture not found")
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = folder / f"photo{ext}"
        if p.exists():
            return FileResponse(p)
    raise HTTPException(status_code=404, detail="Photo not found")


@app.get("/api/fixtures/{fixture_id}/ies")
def fixture_ies(fixture_id: str):
    folder = _fixture_dir_by_id(fixture_id)
    if not str(folder).startswith(str(FIXTURES_LIBRARY_DIR.resolve())) or not folder.exists():
        raise HTTPException(status_code=404, detail="Fixture not found")
    path = folder / "profile.ies"
    if not path.exists():
        raise HTTPException(status_code=404, detail="IES not found")
    return FileResponse(path, media_type="application/octet-stream", filename=f"{fixture_id}.ies")


@app.post("/api/projects/{project_id}/fixtures/{fixture_id}/add")
def add_fixture_to_project(project_id: str, fixture_id: str) -> dict:
    base = project_dir(project_id)
    folder = _fixture_dir_by_id(fixture_id)
    if not str(folder).startswith(str(FIXTURES_LIBRARY_DIR.resolve())) or not folder.exists():
        raise HTTPException(status_code=404, detail="Fixture not found")
    ies = folder / "profile.ies"
    if not ies.exists():
        raise HTTPException(status_code=404, detail="IES not found")
    copied = copy_unique(ies, base / "ies_library", ies.name)
    meta_path = folder / "meta.json"
    name = fixture_id
    if meta_path.exists():
        try:
            name = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("name") or name
        except Exception:
            pass
    write_project_meta(base, {
        "dealer_product_id": f"fixture:{fixture_id}",
        "dealer_product_name": name,
        "ies_count": len([p for p in (base / "ies_library").glob("*") if p.is_file() and p.suffix.lower() == ".ies"]),
        "status": "fixture_added",
    })
    append_pipeline_log(base, "fixture_added", {"fixture_id": fixture_id, "ies": copied.name, "name": name})
    return get_project(project_id)


@app.post("/api/admin/fixtures")
async def admin_add_fixture(
    password: str = Form(...),
    name: str = Form(...),
    photo: UploadFile = File(...),
    ies: UploadFile = File(...),
) -> dict:
    _require_catalog_password(password)
    base_id = safe_name(name).replace(" ", "_").lower()
    base_id = re.sub(r"_+", "_", base_id).strip("_") or uuid.uuid4().hex[:10]
    fixture_id = base_id
    folder = FIXTURES_LIBRARY_DIR / fixture_id
    idx = 2
    while folder.exists():
        fixture_id = f"{base_id}_{idx}"
        folder = FIXTURES_LIBRARY_DIR / fixture_id
        idx += 1
    folder.mkdir(parents=True, exist_ok=True)
    # photo
    ext = (Path(photo.filename or "").suffix or ".jpg").lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    await save_upload(photo, folder / f"photo{ext}")
    # ies
    if (Path(ies.filename or "").suffix or "").lower() != ".ies":
        raise HTTPException(status_code=400, detail="IES-файл должен иметь расширение .ies")
    await save_upload(ies, folder / "profile.ies")
    (folder / "meta.json").write_text(json.dumps({"name": name.strip()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "fixture": {"id": fixture_id, "name": name.strip()}}


@app.delete("/api/admin/fixtures/{fixture_id}")
def admin_delete_fixture(fixture_id: str, password: str = Form(...)) -> dict:
    _require_catalog_password(password)
    folder = _fixture_dir_by_id(fixture_id)
    if not str(folder).startswith(str(FIXTURES_LIBRARY_DIR.resolve())) or not folder.exists():
        raise HTTPException(status_code=404, detail="Fixture not found")
    shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


@app.post("/api/library-import-existing")
def import_existing_library() -> dict:
    scenario_count = sync_scenarios_to_style_library()
    imported = import_existing_to_library()
    imported["scenarios"] = scenario_count
    imported["ies_photos"] = sync_ies_catalog_photos()
    return {"ok": True, "imported": imported, "library": library()}


@app.get("/api/library/{kind}/file/{file_path:path}")
def get_library_file(kind: Literal["source", "ies", "style"], file_path: str):
    target = resolve_library_file(kind, file_path)
    return FileResponse(target)


@app.post("/api/projects/{project_id}/library/{kind}")
def add_library_to_project(project_id: str, kind: Literal["source", "ies", "style"], relative_path: str = Form(...)) -> dict:
    base = project_dir(project_id)
    src = resolve_library_file(kind, relative_path)

    if kind == "source":
        copied = copy_unique(src, base / "input", src.name)
        save_rgb(copied, base / "input" / "building.png")
        write_project_meta(base, {"status": "source_selected", "source_name": src.name})
    elif kind == "style":
        copied = copy_unique(src, base / "references", src.name)
        save_rgb(copied, base / "references" / "style_reference_target.png")
        write_project_meta(base, {"style_name": src.name})
    else:
        copy_ies_with_photo(src, base / "ies_library")
        write_project_meta(base, {"ies_count": len(list((base / "ies_library").glob("*.ies"))) + len(list((base / "ies_library").glob("*.IES")))})

    return get_project(project_id)


ADMIN_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS Admin · История сессий</title>
  <style>
    :root{--bg:#070a0e;--panel:#0d1218;--line:#27313b;--text:#e8eef6;--muted:#9aa6b2;--accent:#5a8fd4}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 Segoe UI,Arial,sans-serif}
    header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--line);background:#0a0e14}
    h1{margin:0;font-size:18px}
    .muted{color:var(--muted)}
    .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
    input,select,button{border-radius:10px;border:1px solid var(--line);background:#121820;color:var(--text);padding:9px 12px;font:inherit}
    button{cursor:pointer;background:#d8e0ea;color:#05070a;font-weight:700;border:0}
    button.secondary{background:#151b22;color:var(--text);border:1px solid var(--line)}
    main{padding:18px 20px 40px;max-width:1280px;margin:0 auto}
    .stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
    .stat{border:1px solid var(--line);border-radius:12px;padding:10px 14px;background:var(--panel);min-width:120px}
    .stat b{display:block;font-size:20px}
    .tabs{display:flex;gap:8px;margin:0 0 14px}
    .tabs button{background:#151b22;color:var(--text);border:1px solid var(--line)}
    .tabs button.active{background:#1e2a3a;border-color:var(--accent);color:#dce9f8}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
    .card{border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow:hidden;display:flex;flex-direction:column}
    .thumbs{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line)}
    .thumbs a,.thumbs div{background:#030405;min-height:110px;display:grid;place-items:center;color:var(--muted);font-size:12px}
    .thumbs img{width:100%;height:110px;object-fit:cover;display:block}
    .body{padding:12px;display:grid;gap:6px}
    .body .title{font-weight:700;font-size:13px;word-break:break-all}
    .meta{font-size:12px;color:var(--muted);line-height:1.4}
    .vote.like{color:#8fd48f}.vote.dislike{color:#e89a9a}
    .actions{display:flex;gap:8px;margin-top:6px}
    .actions a{font-size:12px;color:#9ec5ff;text-decoration:none}
    .list{display:grid;gap:12px}
    .hist{display:grid;grid-template-columns:140px 1fr;gap:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:10px;align-items:start}
    .hist img{width:140px;height:90px;object-fit:cover;border-radius:8px;background:#030405}
    .hist details{margin-top:8px}
    .hist pre{white-space:pre-wrap;word-break:break-word;max-height:220px;overflow:auto;background:#070a0e;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:11px;color:#c8d4e0}
    .empty{padding:28px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);text-align:center}
    .err{color:#e89a9a;margin:8px 0}
    .login{max-width:420px;margin:12vh auto;padding:24px;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .login h2{margin:0 0 8px;font-size:20px}
    .login p{margin:0 0 14px}
    .login .row{margin-top:10px}
    .hidden{display:none}
  </style>
</head>
<body>
{{MAX_GROUP_WIDGET}}
<header>
  <div>
    <h1>История сессий и размещений</h1>
    <div class="muted" id="subtitle">NITEOS Admin</div>
  </div>
  <div class="row">
    <a class="muted" href="/dealer" style="color:#9ec5ff;text-decoration:none">← К генерации</a>
    <button type="button" class="secondary" id="logoutBtn" onclick="logout()">Выйти</button>
  </div>
</header>

<div class="login" id="loginBox">
  <h2>Вход в админку</h2>
  <p class="muted">Пароль из `.env` — `CATALOG_ADMIN_PASSWORD`.</p>
  <input id="passwordInput" type="password" placeholder="Пароль" style="width:100%" onkeydown="if(event.key==='Enter')login()">
  <div class="row">
    <button type="button" onclick="login()">Открыть</button>
  </div>
  <div class="err hidden" id="loginErr"></div>
</div>

<main id="app" class="hidden">
  <div class="stats" id="stats"></div>
  <div class="finetune-box" id="finetuneBox" style="margin:0 0 16px;padding:12px 14px;border:1px solid #2b333d;border-radius:12px;background:#0c1218">
    <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
      <div>
        <b>Датасет LoRA</b>
        <div class="muted" id="finetuneSummary" style="margin-top:4px">Загрузка…</div>
      </div>
      <button type="button" class="secondary" onclick="rebuildFinetuneDataset()">Пересобрать датасет</button>
    </div>
  </div>
  <div class="tabs">
    <button type="button" class="active" id="tabSessions" onclick="showTab('sessions')">Сессии</button>
    <button type="button" id="tabHistory" onclick="showTab('history')">Рендеры / размещения</button>
  </div>
  <div class="row" style="margin-bottom:14px">
    <select id="filterMode" onchange="reload()">
      <option value="">Все режимы</option>
      <option value="auto">Только авто</option>
      <option value="manual">Только вручную</option>
    </select>
    <select id="filterVote" onchange="reload()">
      <option value="">Любой feedback</option>
      <option value="like">Like</option>
      <option value="dislike">Dislike</option>
      <option value="none">Без оценки</option>
    </select>
    <button type="button" class="secondary" onclick="reload()">Обновить</button>
  </div>
  <div id="sessionsView"></div>
  <div id="historyView" class="hidden"></div>
  <div class="err hidden" id="loadErr"></div>
</main>

<script>
const PASS_KEY = 'niteos_admin_pass';
let password = localStorage.getItem(PASS_KEY) || '';
let tab = 'sessions';
let sessions = [];
let historyItems = [];
let stats = {};

function esc(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function qs(extra){
  const p = new URLSearchParams({password, ...(extra||{})});
  return p.toString();
}
async function api(path){
  const res = await fetch(path);
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail || res.statusText || 'Ошибка');
  return data;
}
function login(){
  password = (document.getElementById('passwordInput').value || '').trim();
  if(!password){ showLoginErr('Введите пароль'); return; }
  localStorage.setItem(PASS_KEY, password);
  boot();
}
function logout(){
  localStorage.removeItem(PASS_KEY);
  password = '';
  document.getElementById('app').classList.add('hidden');
  document.getElementById('loginBox').classList.remove('hidden');
}
function showLoginErr(msg){
  const el = document.getElementById('loginErr');
  el.textContent = msg;
  el.classList.toggle('hidden', !msg);
}
function showTab(name){
  tab = name;
  document.getElementById('tabSessions').classList.toggle('active', name==='sessions');
  document.getElementById('tabHistory').classList.toggle('active', name==='history');
  document.getElementById('sessionsView').classList.toggle('hidden', name!=='sessions');
  document.getElementById('historyView').classList.toggle('hidden', name!=='history');
}
function matchesFilters(item){
  const mode = document.getElementById('filterMode').value;
  const vote = document.getElementById('filterVote').value;
  const wm = (item.work_mode || '').toLowerCase();
  if(mode === 'auto' && wm !== 'auto') return false;
  if(mode === 'manual' && wm === 'auto') return false;
  const v = (item.feedback_vote || item.last_feedback_vote || '').toLowerCase();
  if(vote === 'like' && v !== 'like') return false;
  if(vote === 'dislike' && v !== 'dislike') return false;
  if(vote === 'none' && v) return false;
  return true;
}
function voteHtml(v){
  if(v==='like') return '<span class="vote like">👍 like</span>';
  if(v==='dislike') return '<span class="vote dislike">👎 dislike</span>';
  return '<span class="muted">без оценки</span>';
}
function feedbackStatusHtml(h){
  const st = (h.feedback_status || '').toLowerCase();
  if(st === 'submitted' || h.feedback_vote) return voteHtml(h.feedback_vote || h.last_feedback_vote);
  if(st === 'skipped') return '<span class="muted">оценка пропущена</span>';
  return '<span class="muted">ожидает оценку</span>';
}
function renderStats(){
  document.getElementById('stats').innerHTML = `
    <div class="stat"><b>${stats.sessions ?? 0}</b><span class="muted">сессий</span></div>
    <div class="stat"><b>${stats.withFinal ?? 0}</b><span class="muted">с финалом</span></div>
    <div class="stat"><b>${stats.history ?? 0}</b><span class="muted">рендеров</span></div>
    <div class="stat"><b>${stats.feedback ?? 0}</b><span class="muted">feedback файлов</span></div>
    <div class="stat"><b>${stats.generations ?? 0}</b><span class="muted">архивов генераций</span></div>
    <div class="stat"><b>${stats.learning ?? 0}</b><span class="muted">learning events</span></div>
    <div class="stat"><b>${stats.finetuneTotal ?? 0}</b><span class="muted">LoRA samples</span></div>
  `;
}
async function loadFinetuneStats(){
  const el = document.getElementById('finetuneSummary');
  if(!el) return;
  try{
    const d = await api('/api/admin/finetune-dataset?' + qs());
    stats.finetuneTotal = d.total || d.train_images || 0;
    const votes = d.by_vote || {};
    const kinds = d.by_kind || {};
    el.textContent = [
      `пар: ${d.total || 0}`,
      `train img: ${d.train_images || 0}`,
      `сценариев: ${d.scenarios || 0}`,
      `like/dislike: ${votes.like || 0}/${votes.dislike || 0}`,
      d.endpoint_configured ? 'endpoint: ON' : 'endpoint: soft few-shot',
      kinds.mvp_fixture ? `fixtures: ${kinds.mvp_fixture}` : '',
      kinds.viz_example ? `viz: ${kinds.viz_example}` : '',
    ].filter(Boolean).join(' · ');
  }catch(err){
    el.textContent = 'Датасет ещё не собран (или ошибка): ' + String(err.message || err);
  }
}
async function rebuildFinetuneDataset(){
  const el = document.getElementById('finetuneSummary');
  if(el) el.textContent = 'Сборка датасета…';
  try{
    const fd = new FormData();
    fd.append('password', password);
    const res = await fetch('/api/admin/finetune-dataset/rebuild', {method:'POST', body: fd});
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(data.detail || res.statusText);
    await loadFinetuneStats();
    renderStats();
  }catch(err){
    if(el) el.textContent = 'Ошибка сборки: ' + String(err.message || err);
  }
}
function renderSessions(){
  const items = sessions.filter(matchesFilters);
  const box = document.getElementById('sessionsView');
  if(!items.length){
    box.innerHTML = '<div class="empty">Сессий по фильтру нет</div>';
    return;
  }
  box.innerHTML = `<div class="grid">${items.map(s => `
    <article class="card">
      <div class="thumbs">
        ${s.source_url ? `<a href="${esc(s.source_url)}" target="_blank"><img src="${esc(s.source_url)}?t=1" alt="source"></a>` : `<div>нет source</div>`}
        ${s.final_url ? `<a href="${esc(s.final_url)}" target="_blank"><img src="${esc(s.final_url)}?t=1" alt="final"></a>` : `<div>нет final</div>`}
      </div>
      <div class="body">
        <div class="title">${esc(s.project_name || s.project_id)}</div>
        <div class="meta">
          ${esc(s.updated_at || '')}<br>
          режим: <b>${esc(s.work_mode || '—')}</b> · статус: ${esc(s.status || '—')}<br>
          сценарий/эталон: ${esc(s.scenario_name || s.auto_viz_ref || '—')}<br>
          размещение: ${esc(s.placement_family || '—')}${s.placement_strategy ? ' / ' + esc(s.placement_strategy) : ''}<br>
          история: ${esc(s.render_history_count || 0)} · ${voteHtml(s.last_feedback_vote)}
          ${s.last_feedback_comment ? `<br>комментарий: ${esc(s.last_feedback_comment)}` : ''}
          ${s.last_feedback_contact ? `<br>контакт: ${esc(s.last_feedback_contact)}` : ''}
        </div>
        <div class="actions">
          <a href="${esc(s.dealer_url)}" target="_blank">Открыть в dealer</a>
          ${s.style_url ? `<a href="${esc(s.style_url)}" target="_blank">Эталон</a>` : ''}
        </div>
      </div>
    </article>
  `).join('')}</div>`;
}
function renderHistory(){
  const items = historyItems.filter(matchesFilters);
  const box = document.getElementById('historyView');
  if(!items.length){
    box.innerHTML = '<div class="empty">Рендеров по фильтру нет</div>';
    return;
  }
  box.innerHTML = `<div class="list">${items.map(h => `
    <article class="hist">
      ${h.url ? `<a href="${esc(h.url)}" target="_blank"><img src="${esc(h.url)}?t=1" alt=""></a>` : `<div class="muted">нет файла</div>`}
      <div>
        <div class="title">#${esc(h.history_id)} · ${esc(h.kind)} · ${esc(h.project_id)}</div>
        <div class="meta">
          ${esc(h.created_at || '')}<br>
          режим: <b>${esc(h.work_mode || '—')}</b> · модель: ${esc(h.routerai_model || '—')}<br>
          сценарий/эталон: ${esc(h.scenario_name || h.auto_viz_ref || '—')}<br>
          размещение: ${esc(h.placement_family || '—')}${h.placement_strategy ? ' / ' + esc(h.placement_strategy) : ''}<br>
          продукт: ${esc(h.product_name || '—')}${Array.isArray(h.ies_names) && h.ies_names.length ? ' · IES: ' + esc(h.ies_names.join(', ')) : ''}<br>
          ${feedbackStatusHtml(h)}
          ${h.feedback_comment ? `<br><b>комментарий:</b> ${esc(h.feedback_comment)}` : ''}
          ${h.feedback_contact ? `<br><b>контакт:</b> ${esc(h.feedback_contact)}` : ''}
          ${h.feedback_issue_type ? `<br>issue: ${esc(h.feedback_issue_type)}` : ''}
          ${h.generation_archive ? `<br>архив: ${esc(h.generation_archive)}` : ''}
        </div>
        ${(h.prompt || h.prompt_preview) ? `<details><summary>Промпт (${esc((h.prompt || '').length || (h.prompt_preview || '').length)} симв.)</summary><pre>${esc(h.prompt || h.prompt_preview || '')}</pre></details>` : ''}
        <div class="actions">
          <a href="${esc(h.dealer_url)}" target="_blank">Открыть проект</a>
          ${h.source_url ? `<a href="${esc(h.source_url)}" target="_blank">Source</a>` : ''}
          ${h.url ? `<a href="${esc(h.url)}" target="_blank">Рендер</a>` : ''}
          ${h.prompt_url ? `<a href="${esc(h.prompt_url)}" target="_blank">prompt.txt</a>` : ''}
        </div>
      </div>
    </article>
  `).join('')}</div>`;
}
function reload(){
  renderStats();
  renderSessions();
  renderHistory();
}
async function boot(){
  showLoginErr('');
  try{
    const [sess, hist] = await Promise.all([
      api('/api/admin/sessions?' + qs({limit:100})),
      api('/api/admin/render-history?' + qs({limit:200})),
    ]);
    sessions = sess.items || [];
    historyItems = hist.items || [];
    stats = {
      sessions: sessions.length,
      withFinal: sessions.filter(s => s.has_final).length,
      history: hist.count || historyItems.length,
      feedback: hist.feedback_files || 0,
      generations: hist.generation_archives || 0,
      learning: hist.learning_events || 0,
    };
    document.getElementById('loginBox').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    document.getElementById('subtitle').textContent = 'Данные с сервера · cloud_data/projects';
    await loadFinetuneStats();
    showTab(tab);
    reload();
  }catch(err){
    document.getElementById('loginBox').classList.remove('hidden');
    document.getElementById('app').classList.add('hidden');
    showLoginErr(String(err.message || err));
  }
}
if(password) boot();
</script>
</body>
</html>
"""


LANDING_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS Concept Light</title>
  <style>
    body{margin:0;min-height:100vh;background:#05070a;color:#eef2f6;font-family:Segoe UI,Arial,sans-serif;display:grid;place-items:center;padding:24px;opacity:1;transition:opacity .45s ease, transform .45s ease}
    body.leaving{opacity:0;transform:translateY(8px)}
    .wrap{max-width:640px;width:100%;text-align:center}
    h1{font-size:34px;margin:0 0 10px;letter-spacing:-.02em}
    .lead{color:#9aa6b2;font-size:16px;line-height:1.55;margin:0 0 32px}
    .cta{display:inline-block;text-decoration:none;border-radius:12px;border:0;padding:16px 36px;font:inherit;font-size:17px;font-weight:700;cursor:pointer;background:#d8e0ea;color:#05070a;transition:transform .2s ease, box-shadow .2s ease}
    .cta:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(216,224,234,.18)}
    .cta.secondary{background:#151b22;color:#eef2f6;border:1px solid #2b333d}
    .cta.secondary:hover{box-shadow:0 8px 28px rgba(0,0,0,.35)}
    .panel-start,.panel-modes{transition:opacity .3s ease, transform .3s ease}
    .panel-modes{display:none;opacity:0;transform:translateY(10px)}
    .panel-modes.open{display:block;opacity:1;transform:none}
    .panel-start.hide{display:none}
    .modes{display:grid;gap:12px;margin-top:8px}
    @media(min-width:560px){.modes{grid-template-columns:1fr 1fr}}
    .mode-card{display:flex;flex-direction:column;align-items:stretch;gap:10px;text-align:left;text-decoration:none;color:inherit;border:1px solid #2b333d;border-radius:14px;padding:18px;background:#0b0f14;transition:border-color .2s ease, transform .2s ease, box-shadow .2s ease}
    .mode-card:hover{border-color:#5a7a9a;transform:translateY(-2px);box-shadow:0 10px 28px rgba(0,0,0,.35)}
    .mode-card h2{margin:0;font-size:18px;color:#eef2f6}
    .mode-card p{margin:0;color:#9aa6b2;font-size:13px;line-height:1.5;flex:1}
    .mode-card .go{margin-top:4px;display:inline-block;font-size:13px;font-weight:700;color:#f5b942}
    .back{margin-top:18px;background:transparent;border:0;color:#8d97a3;cursor:pointer;font:inherit;font-size:13px;text-decoration:underline;padding:0}
    .back:hover{color:#dbe4ee}
  </style>
</head>
<body>
{{MAX_GROUP_WIDGET}}
<div class="wrap">
  <h1>NITEOS Concept Light</h1>
  <p class="lead">Визуализация архитектурной подсветки фасада с помощью AI</p>

  <div class="panel-start" id="panelStart">
    <button type="button" class="cta" id="startBtn" onclick="goMode(event,'/studio','agent')">Начать генерацию</button>
  </div>

  <!-- Режим «С шаблонами» и выбор режимов временно скрыты — только AI-агент.
  <div class="panel-modes" id="panelModes">
    <p class="lead" style="margin-bottom:18px">Выберите режим</p>
    <div class="modes">
      <a class="mode-card" href="/dealer?welcome=1" onclick="return goMode(event,'/dealer?welcome=1','templates')">
        <h2>С шаблонами</h2>
        <p>Классический режим: сценарии, светильники и ручная настройка подсветки.</p>
        <span class="go">Открыть →</span>
      </a>
      <a class="mode-card" href="/studio" onclick="return goMode(event,'/studio','agent')">
        <h2>AI-агент</h2>
        <p>Студия: сам анализирует фасад, подбирает референс и схему, правит через чат.</p>
        <span class="go">Открыть →</span>
      </a>
    </div>
    <button type="button" class="back" onclick="hideModes()">← Назад</button>
  </div>
  -->
</div>
<script>
/* Выбор режимов временно отключён — «Начать генерацию» сразу ведёт в AI-агент.
function showModes(){
  document.getElementById('panelStart').classList.add('hide');
  const panel = document.getElementById('panelModes');
  panel.style.display = 'block';
  requestAnimationFrame(() => panel.classList.add('open'));
}
function hideModes(){
  const panel = document.getElementById('panelModes');
  panel.classList.remove('open');
  setTimeout(() => {
    panel.style.display = 'none';
    document.getElementById('panelStart').classList.remove('hide');
  }, 280);
}
*/
function goMode(e, href, mode){
  if(e && e.preventDefault) e.preventDefault();
  try{
    sessionStorage.setItem('niteos_from_landing','1');
    sessionStorage.setItem('niteos_landing_mode', mode || 'agent');
  }catch(_){}
  document.body.classList.add('leaving');
  setTimeout(()=>{ window.location.href = href; }, 420);
  return false;
}
</script>
</body>
</html>
"""

DEALER_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS Concept Light</title>
  <style>
    body{margin:0;background:#05070a;color:#eef2f6;font-family:Segoe UI,Arial,sans-serif;opacity:0;animation:dealerFadeIn .45s ease forwards;padding-bottom:78px}
    @keyframes dealerFadeIn{to{opacity:1}}
    main.dealer-page{max-width:1280px;margin:0 auto;padding:20px 20px 48px;display:block}
    section.panel{border:1px solid #2b333d;background:#0b0f14;border-radius:14px;padding:18px;margin-bottom:16px}
    section{border:1px solid #2b333d;background:#0b0f14;border-radius:12px;padding:16px}
    h1{font-size:26px;margin:0} h2{font-size:15px;color:#cbd5e1;margin:0 0 10px;font-weight:700}
    label{display:block;margin:10px 0 6px;color:#9aa6b2;font-size:13px}
    input,textarea,select,button{width:100%;box-sizing:border-box;border-radius:10px;border:1px solid #34404c;background:#070a0e;color:#eef2f6;padding:10px;font:inherit}
    select{
      appearance:none;-webkit-appearance:none;cursor:pointer;
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%239aa6b2' d='M1 1l5 5 5-5'/%3E%3C/svg%3E");
      background-repeat:no-repeat;background-position:right 12px center;padding-right:36px;
    }
    select:focus,textarea:focus,input:focus{outline:none;border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.28)}
    textarea{min-height:150px;resize:vertical}
    #prompt{min-height:min(38vh,340px);max-height:min(52vh,480px);font-size:13px;line-height:1.52}
    button{background:#d8e0ea;color:#05070a;font-weight:700;cursor:pointer;margin-top:10px}
    button.secondary{background:#151b22;color:#eef2f6}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    img{max-width:100%;border-radius:10px;border:1px solid #27313b;background:#030405}
    .muted{color:#8d97a3;font-size:13px}
    .library{display:grid;grid-template-columns:1fr;gap:8px;margin:8px 0 14px}
    .lib-item{display:grid;grid-template-columns:52px 1fr 86px;gap:8px;align-items:center;border:1px solid #27313b;border-radius:10px;padding:7px;background:#070a0e}
    .lib-item.lib-ies-photo{grid-template-columns:72px 1fr 86px}
    .lib-item img{width:64px;height:44px;object-fit:cover;border-radius:6px;background:#030405}
    .lib-item.lib-ies-photo img{width:72px;height:56px;object-fit:contain}
    .lib-item .name{font-size:12px;color:#dbe4ee;overflow:hidden;text-overflow:ellipsis}
    .lib-item button{margin:0;padding:8px;font-size:12px}
    .field-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:12px 0 6px}
    .field-head label{margin:0}
    .field-head button{width:auto;margin:0;padding:7px 10px;font-size:12px}
    .mini-upload{display:grid;grid-template-columns:1fr 122px;gap:8px;margin:8px 0}
    .mini-upload button{margin:0}
    .hidden{display:none}
    .data-card{border:1px solid #2b333d;background:#090d12;border-radius:12px;padding:14px;margin:0 0 12px}
    .step-title{display:flex;align-items:center;gap:10px;margin-bottom:10px;font-weight:700}
    .badge{width:28px;height:28px;border-radius:9px;background:#d8e0ea;color:#05070a;display:inline-grid;place-items:center}
    .preview-box{height:160px;border:1px solid #27313b;border-radius:12px;background:#05070a;display:grid;place-items:center;color:#8d97a3;overflow:hidden;margin-bottom:10px;outline:none}
    .preview-box:focus,.preview-box.paste-hover{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.35)}
    .preview-box img{width:100%;height:100%;object-fit:contain;border:0;border-radius:0}
    .status-line{color:#8d97a3;font-size:13px;margin:0 0 10px;min-height:18px}
    .button-row{display:grid;grid-template-columns:1fr 170px;gap:8px}
    .button-row button{margin:0}
    .button-row .main-action{background:#d8e0ea;color:#05070a}
    .library-panel{display:none;margin-top:10px}
    .library-panel.open{display:block}
    .result-stage{position:relative;border:1px solid #27313b;border-radius:12px;background:#030405;min-height:min(36vh,320px);max-height:min(78vh,760px);display:flex;align-items:center;justify-content:center;overflow:hidden;padding:10px}
    .result-stage img{max-width:100%;max-height:min(76vh,740px);width:auto;height:auto;border:0;border-radius:6px;display:block;object-fit:contain;pointer-events:none;user-select:none}
    .result-stage canvas.result-markup-canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:crosshair;z-index:2}
    .result-stage canvas.result-markup-canvas.hidden{display:none}
    .result-stage.is-editing{outline:2px solid #5a8fd4;outline-offset:1px}
    .edit-section{margin-top:16px;border:1px solid #2b333d;border-radius:12px;padding:12px;background:#090d12}
    .edit-section.collapsed{border:none;padding:0;margin-top:0;background:transparent}
    .edit-section.collapsed #editBtnHint{display:none}
    .edit-section.collapsed .edit-tools{display:none}
    .edit-section .edit-tools{margin-top:12px}
    .render-history-panel{margin:14px 0 4px}
    .render-history-panel.hidden{display:none}
    .render-history-head{font-size:13px;font-weight:700;color:#cbd5e1;margin:0 0 8px}
    .render-history-strip{display:flex;gap:10px;overflow-x:auto;padding:4px 2px 8px}
    .render-history-strip::-webkit-scrollbar{height:7px}
    .render-history-strip::-webkit-scrollbar-thumb{background:#34404c;border-radius:4px}
    .render-history-item{flex:0 0 108px;border:2px solid #27313b;border-radius:10px;background:#070a0e;padding:6px;cursor:pointer;text-align:left}
    .render-history-item:hover,.render-history-item.active{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.22)}
    .render-history-item img{display:block;width:100%;height:68px;object-fit:cover;border-radius:6px;background:#030405;margin-bottom:5px}
    .render-history-item span{display:block;font-size:10px;color:#9aa6b2;line-height:1.25}
    .edit-markup-panel{border:1px solid #3a4d63;border-radius:14px;padding:12px;margin:12px 0;background:#070a0e}
    .edit-markup-panel.hidden{display:none}
    .edit-markup-toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
    .edit-markup-toolbar button{width:auto;margin:0;padding:8px 12px;font-size:13px}
    .edit-markup-toolbar button.active{background:#2a3a4f;border-color:#5a7a9a;color:#e8eef6}
    .edit-markup-toolbar .brush-size{display:flex;align-items:center;gap:8px;font-size:12px;color:#9aa6b2}
    .edit-markup-toolbar .brush-size input{width:120px;margin:0}
    .edit-markup-stage{position:relative;border:1px solid #27313b;border-radius:12px;background:#030405;overflow:hidden;min-height:min(42vh,360px);max-height:min(72vh,680px);touch-action:none}
    .edit-markup-stage img{display:block;width:100%;height:auto;max-height:min(72vh,680px);object-fit:contain;pointer-events:none;user-select:none}
    .edit-markup-stage canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:crosshair}
    .edit-markup-hint{margin:8px 0 0;font-size:12px;color:#8d97a3;line-height:1.45}
    .tool-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0}
    .tool-row.result-actions-row{display:flex;flex-wrap:wrap;gap:8px}
    .tool-row.result-actions-row button{flex:1;min-width:120px;margin:0}
    .tool-row button{margin:0}
    #dealerEditBtn{background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;border:1px solid #f5c966;font-weight:800}
    #dealerEditBtn:disabled{opacity:.42;cursor:not-allowed;filter:none;transform:none;box-shadow:none}
    .top-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
    .top-actions button{margin:0}
    .history-panel{display:none;border:1px solid #27313b;border-radius:12px;background:#070a0e;padding:10px;margin:10px 0 14px;max-height:360px;overflow:auto}
    .history-panel.open{display:block}
    .project-card{border:1px solid #27313b;border-radius:10px;padding:10px;margin-bottom:8px;background:#090d12}
    .project-card .title{font-weight:700;color:#e8eef6;margin-bottom:4px}
    .project-card .meta{color:#8d97a3;font-size:12px;line-height:1.45}
    .project-card button{margin-top:8px}
    details{border:1px solid #27313b;border-radius:12px;padding:10px;margin:12px 0;background:#070a0e}
    summary{cursor:pointer;color:#cbd5e1;font-weight:700}
    #lightImg{margin-top:10px}
    .artifacts-links{display:flex;flex-wrap:wrap;gap:8px 14px;margin:10px 0}
    .artifacts-links a{color:#9ec5ff;text-decoration:none;font-size:13px}
    .artifacts-links a:hover{text-decoration:underline}
    .log-panel{display:none;border:1px solid #27313b;border-radius:12px;background:#070a0e;padding:10px;margin:10px 0 14px;max-height:420px;overflow:auto}
    .log-panel.open{display:block}
    .log-entry{border-bottom:1px solid #1d2530;padding:10px 0}
    .log-entry:last-child{border-bottom:0}
    .log-entry .head{color:#9ec5ff;font-size:12px;margin-bottom:6px}
    .log-entry pre{white-space:pre-wrap;word-break:break-word;margin:0;color:#dbe4ee;font-size:12px;line-height:1.45}
    .back-link{display:inline-flex;align-items:center;gap:6px;margin-bottom:12px;color:#05070a;text-decoration:none;font-size:13px;font-weight:700;background:#d8e0ea;border:1px solid #c5ced9;border-radius:10px;padding:8px 14px;position:relative;z-index:5}
    .back-link:hover{text-decoration:none;background:#e8eef6}
    .page-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;position:relative;z-index:5;flex-wrap:wrap}
    .page-head h1{margin:0}
    .page-head .head-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;position:relative;z-index:5}
    .help-btn{width:auto;margin:0;padding:8px 12px;font-size:12px}
    .help-btn-promo{background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;border:1px solid #f5c966;border-radius:10px;padding:9px 16px;font:inherit;font-weight:700;font-size:13px;cursor:pointer;box-shadow:0 2px 12px rgba(245,185,66,.32);flex-shrink:0}
    .help-btn-promo:hover{filter:brightness(1.06)}
    .result-edit-btn.help-btn-promo{width:auto;min-height:42px;font-size:13px;padding:9px 14px}
    .result-edit-btn.help-btn-promo.active{box-shadow:0 0 0 2px rgba(245,185,66,.45)}
    .result-edit-btn.help-btn-promo:disabled{opacity:.45;cursor:not-allowed;filter:none}
    .tour-focus-pulse{animation:tourPulse 1.4s ease-in-out infinite;position:relative;z-index:100003}
    @keyframes tourPulse{0%,100%{box-shadow:0 0 0 0 rgba(245,185,66,.55)}50%{box-shadow:0 0 0 10px rgba(245,185,66,0)}}
    .tour-wait-hint{margin:12px 0 0;padding:10px 12px;border-radius:10px;background:rgba(245,185,66,.12);border:1px solid rgba(245,185,66,.35);color:#f5e6b8;font-size:13px;line-height:1.45}
    .help-dot.locked{opacity:.35;cursor:default;pointer-events:none}
    .welcome-tour-root{position:fixed;inset:0;z-index:100010;display:none}
    .welcome-tour-root.open{display:block;pointer-events:auto}
    .welcome-tour-card{position:fixed;z-index:100012;left:50%;top:50%;transform:translate(-50%,-50%);width:min(420px,calc(100vw - 32px));border:1px solid #f5c966;border-radius:14px;background:#0b0f14;padding:20px;box-shadow:0 16px 48px rgba(0,0,0,.7);pointer-events:auto}
    .welcome-tour-card h3{margin:0 0 10px;font-size:18px;color:#f5e6b8}
    .welcome-tour-card p{margin:0 0 10px;color:#cbd5e1;font-size:14px;line-height:1.55}
    .welcome-tour-card .actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
    .welcome-tour-card .actions button{width:auto;margin:0}
    .welcome-tour-arrow{position:fixed;z-index:100013;width:0;height:0;border-left:10px solid transparent;border-right:10px solid transparent;border-bottom:12px solid #f5c966;display:none}
    .tour-root{position:fixed;inset:0;z-index:100000;display:none;pointer-events:none}
    .tour-root.open{display:block}
    .tour-dim{position:fixed;background:rgba(5,7,10,.78);pointer-events:none;z-index:100000;display:none}
    .tour-spotlight{position:fixed;z-index:100001;border:2px solid #f5b942;border-radius:14px;box-shadow:0 0 28px rgba(245,185,66,.45);pointer-events:none;background:transparent;transition:top .4s ease,left .4s ease,width .4s ease,height .4s ease;display:none}
    .tour-target-active{position:relative;pointer-events:auto}
    .tour-card{position:fixed;z-index:100002;pointer-events:auto;right:16px;top:16px;bottom:16px;width:min(380px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow-y:auto;border:1px solid #3a4d63;border-radius:14px;background:#0b0f14;padding:18px;box-shadow:0 16px 48px rgba(0,0,0,.65);display:none}
    .tour-card.open{display:block}
    .tour-card .help-step-meta{display:flex;align-items:center;gap:12px;margin-bottom:8px}
    .tour-card .help-step-badge{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;display:grid;place-items:center;font-weight:800;font-size:16px;flex-shrink:0}
    .tour-card .help-step-meta h3{margin:0;flex:1;font-size:17px}
    .tour-card .help-step-counter{font-size:12px;color:#6b7580;margin-bottom:10px}
    .tour-card .help-dots{display:flex;justify-content:center;gap:7px;margin-bottom:12px}
    .tour-card .help-dot{width:9px;height:9px;border-radius:50%;background:#34404c;cursor:pointer;transition:background .2s,transform .15s}
    .tour-card .help-dot:hover{background:#5a7a9a}
    .tour-card .help-dot.active{background:#f5b942;transform:scale(1.25)}
    .tour-card .help-lead{margin:0 0 10px;color:#9aa6b2;font-size:13px;line-height:1.5}
    .tour-actions{margin-top:10px;padding:10px 12px;background:#111820;border:1px solid #27313b;border-radius:10px}
    .tour-actions .label{font-size:11px;text-transform:uppercase;color:#f5b942;margin-bottom:6px;letter-spacing:.05em;font-weight:700}
    .tour-actions ul{margin:0;padding-left:18px;color:#e8eef6;font-size:13px;line-height:1.55}
    .tour-actions li{margin-bottom:5px}
    .tour-actions li:last-child{margin-bottom:0}
    .tour-nav{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;margin-top:14px}
    .tour-nav button{width:auto;margin:0;min-width:96px;pointer-events:auto;cursor:pointer}
    .tour-nav .tour-skip{min-width:auto;padding:8px 12px;color:#9aa6b2;background:transparent;border:1px solid #34404c}
    .tour-nav .tour-skip:hover{color:#e8eef6;border-color:#5a7a9a}
    .tour-nav-main{display:flex;gap:8px;margin-left:auto}
    .tour-nav .help-next{background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;border:1px solid #f5c966;font-weight:700}
    .tour-nav .help-next:hover{filter:brightness(1.06)}
    .tour-nav .help-prev:disabled{opacity:.35;cursor:default;pointer-events:none}
    @media (max-width:900px){
      .tour-card{right:12px;left:12px;width:auto;top:auto;bottom:12px;max-height:min(52vh,420px)}
    }
    .client-steps{display:grid;gap:12px}
    .template-grid{display:grid;grid-template-columns:1fr;gap:10px;margin:10px 0}
    .template-card{display:grid;grid-template-columns:88px 1fr;gap:10px;border:1px solid #27313b;border-radius:12px;padding:10px;background:#070a0e;cursor:pointer}
    .template-card:hover,.template-card.selected{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.25)}
    .template-card img{width:88px;height:66px;object-fit:cover;border-radius:8px;border:1px solid #27313b}
    .template-card .title{font-weight:700;color:#e8eef6;margin-bottom:4px}
    .template-card .desc{font-size:12px;color:#8d97a3;line-height:1.4}
    .client-actions{display:grid;gap:8px}
    .gen-overlay{position:absolute;inset:0;display:none;place-items:center;background:rgba(3,4,5,.78);z-index:5;text-align:center;padding:20px}
    .gen-overlay.open{display:grid}
    .gen-overlay .box{border:1px solid #3a4d63;border-radius:14px;background:#0b1017;padding:18px 22px;max-width:320px}
    .gen-overlay .title{font-weight:700;color:#e8eef6;margin-bottom:8px}
    .gen-overlay .text{font-size:13px;color:#9aa6b2;line-height:1.45}
    .spinner{width:34px;height:34px;border:3px solid #2b333d;border-top-color:#9ec5ff;border-radius:50%;margin:0 auto 12px;animation:spin 1s linear infinite}
    @keyframes spin{to{transform:rotate(360deg)}}
    .mode-panel.hidden{display:none}
    .h-scroll{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 10px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}
    .h-scroll::-webkit-scrollbar{height:7px}
    .h-scroll::-webkit-scrollbar-thumb{background:#34404c;border-radius:4px}
    .scroll-hint{font-size:12px;color:#6b7580;margin:0 0 8px}
    .scenario-catalog-wrap{
      max-height:calc(2 * 178px + 10px);
      overflow-y:auto;
      overflow-x:hidden;
      padding:8px 10px 10px;
      border:1px solid #27313b;
      border-radius:12px;
      background:#05070a;
    }
    .scenario-catalog-wrap::-webkit-scrollbar{width:8px}
    .scenario-catalog-wrap::-webkit-scrollbar-thumb{background:#34404c;border-radius:4px}
    .scenario-catalog-grid{
      display:grid;
      grid-template-columns:repeat(5,minmax(0,1fr));
      gap:10px;
    }
    .scenario-card{min-width:0;border:2px solid #27313b;border-radius:12px;padding:9px;background:#070a0e;cursor:pointer}
    .scenario-card:hover,.scenario-card.selected{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.22)}
    .scenario-card .thumb{height:118px;border-radius:8px;border:1px solid #27313b;background:#030405;overflow:hidden;margin-bottom:7px}
    .scenario-card .thumb.thumb-prompt-stale{border:2px solid #e04545;box-shadow:0 0 0 1px rgba(224,69,69,.35)}
    .scenario-card .thumb img{width:100%;height:100%;object-fit:cover}
    .scenario-card .title{font-weight:700;font-size:12px;color:#e8eef6;margin-bottom:2px}
    .scenario-card .desc{font-size:10px;color:#8d97a3;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    .category-row{margin-bottom:12px}
    @media (max-width:1080px){
      .scenario-catalog-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
    }
    @media (max-width:860px){
      .scenario-catalog-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
    }
    @media (max-width:620px){
      .scenario-catalog-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
    }
    .main-generate{
      width:100%;margin:0;padding:15px 18px;font-size:16px;font-weight:800;
      border:1px solid #f5c966;border-radius:12px;
      background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;
      box-shadow:0 4px 18px rgba(245,185,66,.28);
      transition:filter .15s,transform .15s,opacity .15s;
    }
    .main-generate:hover:not(:disabled){filter:brightness(1.06);transform:translateY(-1px)}
    .main-generate:disabled{opacity:.42;cursor:not-allowed;transform:none;box-shadow:none}
    .main-generate.is-busy{opacity:.72;cursor:wait}
    .generate-panel{
      margin-top:16px;padding:14px 14px 12px;border:1px solid #3a4d63;border-radius:14px;
      background:linear-gradient(180deg,#0c1018 0%,#080b10 100%);
    }
    .generate-panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
    .generate-panel-title{font-size:12px;font-weight:700;color:#cbd5e1;text-transform:uppercase;letter-spacing:.05em}
    .model-pill{font-size:11px;color:#9ec5ff;background:#111820;border:1px solid #34404c;border-radius:999px;padding:4px 10px;max-width:52%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .model-pill.hidden{display:none}
    .generate-panel-inner{display:grid;gap:12px}
    .generate-panel-inner .model-block label{margin-top:0}
    #routeraiModel,#reviewProfile{font-size:13px;line-height:1.35}
    .model-hint{font-size:12px;line-height:1.45;margin:6px 0 0;min-height:18px}
    .generate-reason{font-size:12px;line-height:1.45;margin-top:10px;padding:8px 10px;border-radius:8px;background:rgba(245,185,66,.08);border:1px solid rgba(245,185,66,.22);color:#f5e6b8}
    .generate-reason.hidden{display:none}
    .agent-preview-btn{width:100%;margin:0;padding:12px 14px;font-size:13px;font-weight:700;border:1px solid #3a4d63;border-radius:12px;background:#111820;color:#cbd5e1}
    .work-mode-toggle{display:flex;gap:8px;margin:0 0 12px;flex-wrap:wrap}
    .work-mode-toggle button{min-width:120px;height:38px;border-radius:10px;border:1px solid #3a4552;background:#121820;color:#c8d4e0;font-size:13px;font-weight:700;cursor:pointer}
    .work-mode-toggle button.active{border-color:#5a8fd4;background:#152030;color:#d7e8ff}
    .auto-scenario-panel{border:1px solid #2b3a4c;border-radius:12px;background:#070b10;padding:12px;margin:0 0 12px}
    .auto-scenario-panel .main-action{width:100%;margin:0 0 8px}
    .auto-prompt-preview{white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto;margin:8px 0 0;padding:10px;border-radius:8px;border:1px solid #27313b;background:#090d12;color:#c5d0db;font-size:12px;line-height:1.4}
    .auto-test-card{flex:0 0 148px;scroll-snap-align:start;border:2px solid #27313b;border-radius:12px;padding:8px;background:#070a0e;cursor:pointer}
    .auto-test-card:hover,.auto-test-card.selected{border-color:#5a8fd4;box-shadow:0 0 0 2px rgba(90,143,212,.25)}
    .auto-test-card img{width:100%;height:96px;object-fit:cover;border-radius:8px;border:1px solid #27313b;display:block;margin-bottom:6px}
    .auto-test-card .title{font-size:11px;color:#c8d4e0;line-height:1.3;word-break:break-all}
    .agent-preview-btn:hover:not(:disabled){border-color:#5a7a9a;background:#162131}
    .agent-preview-panel{display:none;margin-top:12px;border:1px solid #34404c;border-radius:12px;background:#070a0e;padding:12px;color:#cbd5e1}
    .agent-preview-panel.open{display:block}
    .agent-preview-panel .head{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px;color:#9ec5ff;font-size:12px;font-weight:700}
    .agent-preview-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0}
    .agent-preview-cell{border:1px solid #27313b;border-radius:8px;background:#090d12;padding:8px;font-size:12px;line-height:1.35}
    .agent-preview-cell strong{display:block;color:#8d97a3;font-weight:600;margin-bottom:2px}
    .agent-preview-list{margin:8px 0 0;padding-left:18px;color:#9aa6b2;font-size:12px;line-height:1.45}
    .agent-preview-list li{margin:2px 0}
    @media (min-width:720px){
      .generate-panel-inner{grid-template-columns:1fr 1fr minmax(220px,34%);align-items:end}
      .generate-panel-inner .main-generate{align-self:stretch;min-height:84px}
    }
    .ies-used-panel{border:1px solid #27313b;border-radius:12px;padding:12px;margin:12px 0;background:#070a0e}
    .render-used-block{border:1px solid #3a4d63;border-radius:14px;padding:16px 18px;margin:18px 0 8px;background:linear-gradient(180deg,#0c1018,#080b10)}
    .render-used-block.hidden{display:none}
    .render-used-title{margin:0 0 12px;font-size:16px;color:#e8eef6;font-weight:700}
    .render-used-meta{margin-bottom:14px}
    .render-used-meta .item{font-size:13px;color:#cbd5e1;padding:2px 0;line-height:1.45}
    .render-used-meta .item strong{color:#9aa6b2;font-weight:600}
    .render-ies-section{border-top:1px solid #27313b;padding-top:14px;margin-top:4px}
    .render-ies-section.hidden{display:none}
    .render-ies-head{font-size:14px;font-weight:700;color:#f5e6b8;margin-bottom:6px}
    .render-ies-note{font-size:12px;color:#8d97a3;line-height:1.5;margin:0 0 10px}
    .render-ies-list{display:flex;flex-direction:column;gap:8px}
    .render-product-card{display:grid;grid-template-columns:88px 1fr;gap:12px;align-items:center;padding:12px;border:1px solid #27313b;border-radius:12px;background:#070a0e}
    .render-product-card img{width:88px;height:68px;object-fit:contain;border-radius:8px;background:#030405;display:block}
    .render-product-card .info{min-width:0}
    .render-product-card .product{font-size:14px;font-weight:700;color:#f5e6b8;margin-bottom:4px}
    .render-product-card .ies{font-size:12px;color:#9aa6b2;line-height:1.4;margin-bottom:8px;word-break:break-word}
    .render-product-card .dl{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#9ec5ff;text-decoration:none}
    .render-product-card .dl:hover{text-decoration:underline}
    .render-product-card .ph{width:88px;height:68px;border-radius:8px;background:#111820;border:1px dashed #34404c;display:grid;place-items:center;color:#6b7580;font-size:11px;text-align:center;padding:6px}
    .render-ies-empty{font-size:13px;color:#8d97a3;margin:0;padding-top:12px;border-top:1px solid #27313b}
    .render-ies-empty.hidden{display:none}
    .render-audit{margin:10px 0 0;padding:9px 11px;border:1px solid #5c5033;border-radius:8px;background:#17130b;color:#f1d895;font-size:12px;line-height:1.4}
    .render-audit.hidden{display:none}
    .ies-used-panel .item{font-size:13px;color:#cbd5e1;padding:3px 0;line-height:1.45}
    .ies-used-panel .item strong{color:#9aa6b2;font-weight:600}
    .ies-used-panel a{color:#9ec5ff;text-decoration:none}
    .ies-used-panel a:hover{text-decoration:underline}
    .workflow-hint{font-size:13px;color:#8d97a3;line-height:1.45;margin:8px 0 12px;padding:10px;border:1px solid #27313b;border-radius:10px;background:#070a0e}
    .workflow-stepper{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 10px}
    .workflow-stepper .s{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:999px;border:1px solid #27313b;background:#070a0e;color:#9aa6b2;font-size:12px;cursor:pointer;user-select:none}
    .workflow-stepper .s .n{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:999px;border:1px solid #34404c;background:#05070a;color:#9aa6b2;font-weight:800;font-size:12px}
    .workflow-stepper .s.active{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.22);color:#e8eef6}
    .workflow-stepper .s.active .n{border-color:#9ec5ff;color:#e8eef6}
    .workflow-stepper .s.done{border-color:#2f5e3c;background:rgba(28,50,34,.35);color:#cfe9d7}
    .workflow-stepper .s.done .n{border-color:#41c36a;color:#cfe9d7}
    .step-block.next-step{border:2px solid #f5b942;border-radius:14px;padding:12px 12px 14px;background:linear-gradient(180deg,rgba(245,185,66,.08),rgba(7,10,14,0));box-shadow:0 0 0 2px rgba(245,185,66,.18)}
    .step-block.next-step .step-head .badge{box-shadow:0 0 0 2px rgba(245,185,66,.25)}
    .ies-preview-row{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 4px}
    .ies-preview-card{width:92px;border:1px solid #27313b;border-radius:10px;background:#070a0e;overflow:hidden}
    .ies-preview-card img{display:block;width:100%;height:68px;object-fit:cover;background:#030405}
    .ies-preview-card .cap{font-size:10px;color:#9aa6b2;padding:5px 6px;line-height:1.25;max-height:34px;overflow:hidden}
    .step-block{margin-bottom:20px}
    .step-block:last-child{margin-bottom:0}
    .step-head{display:flex;align-items:center;gap:10px;margin-bottom:10px;font-weight:700;color:#e8eef6}
    .source-preview-box{min-height:160px;border:1px solid #27313b;border-radius:12px;background:#05070a;display:flex;align-items:center;justify-content:center;color:#8d97a3;overflow:auto;outline:none;padding:10px;text-align:center;font-size:13px;line-height:1.4}
    .source-preview-box.has-image{align-items:flex-start;justify-content:center;padding:6px;max-height:min(72vh,560px)}
    .source-preview-box:focus,.source-preview-box.paste-hover{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.35)}
    .source-preview-box img{display:block;max-width:100%;width:auto;height:auto;max-height:min(70vh,540px);object-fit:contain;border:0;border-radius:6px;margin:0 auto}
    .result-zone{border:1px solid #2b333d;background:#090d12;border-radius:14px;padding:18px;margin-top:8px;transition:border-color .25s,box-shadow .25s}
    .result-zone.empty{display:none}
    .result-zone.scroll-nudge{border-color:#f5b942;box-shadow:0 0 0 2px rgba(245,185,66,.22)}
    .ref-card{flex:0 0 180px;scroll-snap-align:start;border:2px solid #27313b;border-radius:12px;padding:8px;background:#070a0e;cursor:pointer}
    .ref-card:hover,.ref-card.selected{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.22)}
    .ref-card .thumb{height:100px;border-radius:8px;border:1px solid #27313b;background:#030405;overflow:hidden;margin-bottom:6px}
    .ref-card .thumb img{width:100%;height:100%;object-fit:cover}
    .ref-card .title{font-weight:700;font-size:11px;color:#e8eef6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .toolbar-compact{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
    .toolbar-compact button{width:auto;margin:0;padding:8px 12px;font-size:13px}
    .upload-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .upload-row button{width:auto;margin:0}
    .contact-cta-panel{border:2px solid #f5b942;border-radius:16px;padding:20px;margin-top:20px;background:linear-gradient(135deg,#141a10 0%,#0b1017 55%,#101820 100%);box-shadow:0 8px 32px rgba(245,185,66,.12),inset 0 1px 0 rgba(245,185,66,.15)}
    .contact-cta-panel.hidden{display:none}
    .contact-cta-panel h3{margin:0 0 8px;font-size:18px;color:#f5e6b8;font-weight:700}
    .contact-cta-panel .lead{color:#b8c4d0;font-size:14px;line-height:1.55;margin:0 0 14px}
    .feedback-zone{border:1px solid #2b333d;background:#090d12;border-radius:14px;padding:18px;margin-top:16px}
    .feedback-zone.hidden{display:none}
    .feedback-zone h2{margin:0 0 6px;font-size:18px}
    .feedback-zone .lead{margin:0 0 12px;font-size:13px;color:#9aa8b8}
    .feedback-votes{display:flex;gap:10px;margin:0 0 12px;flex-wrap:wrap}
    .feedback-votes button{min-width:140px;height:44px;border-radius:12px;border:1px solid #3a4552;background:#121820;color:#c8d4e0;font-size:14px;font-weight:700;cursor:pointer;transition:background .15s,border-color .15s,color .15s}
    .feedback-votes button.like.active,.feedback-votes button.like:hover{background:#1e2a18;border-color:#7dbe4a;color:#d7f0b8}
    .feedback-votes button.dislike.active,.feedback-votes button.dislike:hover{background:#2a1818;border-color:#e07a7a;color:#f0c0c0}
    .feedback-zone textarea{width:100%;min-height:72px;margin:0 0 10px;resize:vertical}
    .feedback-zone input[type=text]{width:100%;margin:0 0 12px}
    .feedback-zone .feedback-status{margin-top:8px;font-size:13px;color:#8fd48f}
    .feedback-toast{
      position:fixed;bottom:18px;right:18px;max-width:min(340px,calc(100vw - 36px));z-index:80;
      border:1px solid #3a4552;background:#121820;border-radius:14px;padding:14px 40px 14px 16px;
      box-shadow:0 10px 32px rgba(0,0,0,.45);animation:feedbackToastIn .28s ease;
    }
    .feedback-toast.hidden{display:none}
    @keyframes feedbackToastIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
    .feedback-toast-title{margin:0 0 4px;font-size:15px;font-weight:700}
    .feedback-toast-lead{margin:0 0 10px;font-size:12px;line-height:1.45}
    .feedback-toast-actions{display:flex;gap:8px;flex-wrap:wrap}
    .feedback-toast-actions button{width:auto;margin:0;padding:8px 12px;font-size:13px}
    .feedback-toast-close{
      position:absolute;top:8px;right:10px;width:28px;height:28px;border:0;border-radius:8px;
      background:transparent;color:#8d97a3;font-size:20px;line-height:1;cursor:pointer;padding:0;
    }
    .feedback-toast-close:hover{color:#eef2f6;background:#1a222c}
    .contact-phone-btn{display:inline-block;padding:12px 22px;border-radius:12px;background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;font-weight:800;font-size:17px;text-decoration:none;letter-spacing:.02em;box-shadow:0 4px 18px rgba(245,185,66,.35);transition:filter .15s}
    .contact-phone-btn:hover{filter:brightness(1.07)}
    .contact-phone-btn--inline{font-size:15px;padding:10px 18px}
  </style>
</head>
<body>
{{MAX_GROUP_WIDGET}}
<div class="welcome-tour-root" id="welcomeTourRoot">
  <div class="tour-dim" id="welcomeDimTop"></div>
  <div class="tour-dim" id="welcomeDimLeft"></div>
  <div class="tour-dim" id="welcomeDimBottom"></div>
  <div class="tour-dim" id="welcomeDimGap"></div>
  <div class="tour-spotlight" id="welcomeSpotlight"></div>
  <div class="welcome-tour-card" id="welcomeTourCard">
    <h3>Добро пожаловать</h3>
    <p>Хотите лучше понять, как всё работает, и <b>пройти все этапы вместе</b> с подсказками?</p>
    <p>Нажмите <b>«Как это работает?»</b> вверху справа — проведём: фото → сценарий → генерация → результат → оценка.</p>
    <div class="actions">
      <button type="button" class="secondary" onclick="dismissWelcomeTourPrompt()">Сам разберусь</button>
      <button type="button" class="help-btn-promo" style="margin:0" onclick="dismissWelcomeTourPrompt(); openGuidedTour();">Начать обучение</button>
    </div>
  </div>
</div>
<div class="tour-root" id="tourRoot">
  <div class="tour-dim" id="tourDimTop"></div>
  <div class="tour-dim" id="tourDimLeft"></div>
  <div class="tour-dim" id="tourDimBottom"></div>
  <div class="tour-dim" id="tourDimGap"></div>
  <div class="tour-spotlight" id="tourSpotlight"></div>
</div>
<div class="tour-card" id="tourCard">
    <div class="help-step-meta">
      <span class="help-step-badge" id="helpStepBadge">1</span>
      <h3 id="helpTitle">Фото фасада</h3>
    </div>
    <div class="help-step-counter" id="helpStepCounter">Шаг 1 из 5</div>
    <div class="help-dots" id="helpDots"></div>
    <div id="helpBody"></div>
    <div class="tour-nav">
      <button type="button" class="tour-skip" onclick="closeHelp()">Пропустить</button>
      <div class="tour-nav-main">
        <button type="button" class="secondary help-prev" id="helpPrevBtn" onclick="prevHelpStep()">← Назад</button>
        <button type="button" class="help-next" id="helpNextBtn" onclick="helpNextAction()">Далее →</button>
      </div>
    </div>
</div>
<main class="dealer-page">
  <a class="back-link" href="/" id="backHomeBtn">← Назад на главную</a>
  <div class="page-head">
    <div>
      <h1>NITEOS Concept Light</h1>
      <div class="muted" id="projectInfo">Новая генерация · режим шаблонов</div>
    </div>
    <div class="head-actions">
      <a class="help-btn-promo" id="studioLink" href="/studio" style="text-decoration:none;display:inline-flex;align-items:center">AI-студия</a>
      <button class="help-btn-promo" id="helpBtnPromo" onclick="openGuidedTour()">Как это работает?</button>
    </div>
  </div>
  <!-- + Проект / Проекты / Журнал — временно скрыты
  <div class="toolbar-compact" style="display:none">
    <button onclick="createProject()">+ Проект</button>
    <button class="secondary" onclick="toggleProjects()">Проекты</button>
    <button class="secondary" onclick="togglePipelineLog()">Журнал</button>
    <button class="secondary" onclick="downloadPipelineLog()" id="downloadLogBtn" style="display:none">Скачать журнал</button>
  </div>
  -->
  <div class="history-panel" id="projectsPanel" style="display:none"></div>
  <div class="log-panel" id="pipelineLogPanel" style="display:none"><div class="muted">Журнал пуст. Запустите рендер или загрузите данные.</div></div>

  <section class="panel" id="setupPanel">
    <h2>Настройка генерации</h2>
    <div class="muted" style="margin-bottom:16px">Основной путь: фото → сценарий → генерация → оценка. IES подставляются из сценария автоматически.</div>
    <div class="workflow-stepper" id="workflowStepper">
      <div class="s" id="wfS1" onclick="scrollToCard('sourceCard')"><span class="n">1</span><span>Фото</span></div>
      <div class="s" id="wfS2" onclick="scrollToCard('scenariosCard')"><span class="n">2</span><span>Сценарий / шаблон</span></div>
      <div class="s" id="wfS3" onclick="scrollToCard('assignmentCard')"><span class="n">3</span><span>Задание</span></div>
    </div>
    <div class="workflow-hint" id="workflowHint">Шаг 1: загрузите фото фасада.</div>

    <div class="step-block" id="sourceCard">
      <div class="step-head"><span class="badge">1</span><span>Фото фасада</span></div>
      <div class="source-preview-box paste-zone" id="sourcePreviewBox" tabindex="0" title="Ctrl+V или перетащите файл">Фото здания днём · Ctrl+V или перетащите</div>
      <div class="status-line" id="sourceName">Файл не выбран</div>
      <input class="hidden" id="sourceFile" type="file" accept="image/*" onchange="uploadSource()">
      <div class="upload-row">
        <button class="main-action" id="sourceUploadBtn" onclick="chooseFile('sourceFile')">Загрузить</button>
        <button class="secondary" onclick="togglePanel('sourcePanel')">Каталог</button>
      </div>
      <div class="library-panel" id="sourcePanel">
        <div class="library" id="sourceLibrary"></div>
      </div>
    </div>

    <div class="step-block" id="scenariosCard">
      <div class="step-head"><span class="badge">2</span><span>Шаблоны и сценарии</span></div>
      <!-- временно скрыт переключатель Вручную/Авто — только ручной режим
      <div class="work-mode-toggle" id="workModeToggle" role="group" aria-label="Режим подбора шаблона">
        <button type="button" class="active" id="workModeManualBtn" onclick="setDealerWorkMode('manual')">Вручную</button>
        <button type="button" id="workModeAutoBtn" onclick="setDealerWorkMode('auto')">Авто по фото</button>
      </div>
      -->
      <div id="workModeToggle" class="hidden" aria-hidden="true">
        <button type="button" class="active" id="workModeManualBtn" onclick="setDealerWorkMode('manual')">Вручную</button>
      </div>
      <!-- временно скрыт авто-панель
      <div class="auto-scenario-panel hidden" id="autoScenarioPanel">
        <p class="muted" style="margin:0 0 10px">Загрузите своё фото фасада в шаге 1. Затем AI выберет лучший из 20 эталонов света и сразу сделает ночной рендер — либо кликните эталон вручную.</p>
        <div class="muted" style="margin:0 0 6px">Эталоны света (20 примеров виз)</div>
        <div class="h-scroll" id="autoTestPhotoStrip"><div class="muted">Загрузка набора…</div></div>
        <button type="button" class="main-action" id="autoScenarioBtn" onclick="runAutoScenario()" style="margin-top:10px">Авто: выбрать эталон и сгенерировать</button>
        <div class="status-line" id="autoScenarioStatus">Нужно фото фасада. Потом — авто-подбор эталона или клик по карточке.</div>
        <details id="autoPromptDetails" style="margin-top:10px">
          <summary>Промпт переноса света</summary>
          <pre id="autoPromptPreview" class="auto-prompt-preview">Появится после генерации.</pre>
        </details>
      </div>
      -->
      <div id="autoScenarioPanel" class="hidden" aria-hidden="true"></div>
      <div id="manualScenarioPanel">
        <div class="muted" style="margin-bottom:8px"><b>Сценарии</b> — эталон + IES + задание (рекомендуется). <b>Шаблоны</b> — только эталон.</div>
        <div id="dealerScenarioGrid"><div class="muted">Загрузка...</div></div>
      </div>
      <div class="status-line" id="dealerScenarioStatus">Шаблон или сценарий не выбран</div>
      <div class="source-preview-box paste-zone" id="stylePreviewBox" tabindex="0" title="Ctrl+V" style="margin-top:12px">Текущий эталон · Ctrl+V для своего</div>
      <div class="status-line" id="styleName">Эталон не выбран</div>
      <input class="hidden" id="styleFile" type="file" accept="image/*" onchange="uploadStyle()">
      <div class="upload-row">
        <button class="secondary" onclick="chooseFile('styleFile')">Свой эталон</button>
      </div>
    </div>

    <div class="step-block" id="assignmentCard">
      <div class="step-head"><span class="badge">3</span><span>Задание</span></div>
      <label for="facadeMode">Тип фасада</label>
      <select id="facadeMode">
        <option value="auto">Авто</option>
        <option value="classic">Классический фасад</option>
        <option value="modern_glass">Современный стеклянный фасад</option>
      </select>
      <textarea id="prompt" oninput="schedulePromptSave(); updateGenerateControls(lastProjectState);" placeholder="Выберите сценарий — задание подставится автоматически, или введите своё."></textarea>
      <div class="generate-panel" id="generatePanel">
        <div class="generate-panel-head">
          <span class="generate-panel-title">Запуск AI-рендера</span>
          <span class="model-pill hidden" id="routeraiModelPill"></span>
        </div>
        <div class="generate-panel-inner">
          <div class="model-block">
            <label for="routeraiModel">Модель генерации</label>
            <select id="routeraiModel" onchange="onRouteraiModelChange()">
              <option value="">Загрузка моделей…</option>
            </select>
            <div class="model-hint muted" id="routeraiModelHint">У каждой модели — своё типичное время генерации.</div>
          </div>
          <button type="button" class="main-generate" id="generateBtn" onclick="generateVisualization()">
            <span id="generateBtnLabel">Начать генерацию</span>
          </button>
        </div>
        <div class="generate-reason hidden" id="generateBlockReason"></div>
      </div>
      <div class="muted hidden" id="renderLimitHint" style="margin-top:8px"></div>
      <!-- Дополнительно / Артефакты — временно скрыты
      <details style="margin-top:12px">
        <summary>Дополнительно</summary>
        <button class="secondary" onclick="enhancePrompt()">Сжать задание</button>
        <button class="secondary" onclick="packageOnly()">Только пакет</button>
      </details>
      <details id="artifactsPanel">
        <summary>Артефакты последнего запуска</summary>
        <div class="muted" id="artifactsHint">Появятся после генерации</div>
        <div class="artifacts-links" id="artifactsLinks"></div>
        <button class="secondary" onclick="downloadProjectZip()" id="downloadZipBtn" style="display:none">Скачать ZIP</button>
      </details>
      -->
    </div>

    <!-- Свой IES — временно скрыт
    <details class="step-block" id="iesCard" style="margin-top:0">
      <summary class="step-head" style="cursor:pointer;list-style:none"><span class="badge" style="opacity:.65">+</span><span>Свой IES (опционально, без сценария)</span></summary>
      <div class="muted" style="margin:8px 0 10px">При выборе сценария IES подставляются автоматически — этот шаг можно пропустить.</div>
      <div class="preview-box" id="iesStatusBox">IES: нет · подставятся при выборе сценария</div>
      <div class="ies-preview-row hidden" id="iesPreviewRow"></div>
      <div class="status-line" id="iesName">Файлы не выбраны</div>
      <input class="hidden" id="iesFiles" type="file" multiple accept=".ies" onchange="uploadIes()">
      <div class="upload-row">
        <button class="main-action" onclick="chooseFile('iesFiles')">Загрузить</button>
        <button class="secondary" onclick="togglePanel('iesPanel')">Каталог</button>
      </div>
      <div class="library-panel" id="iesPanel">
        <div class="muted" style="margin:0 0 8px">Каталог IES — при наличии фото показывается превью светильника.</div>
        <div class="library" id="iesLibrary"></div>
        <details style="margin-top:12px">
          <summary>Добавить / удалить в каталоге (по паролю)</summary>
          <div class="muted" style="margin:8px 0 10px">Загрузите IES. Фото — по желанию, чтобы было видно, что выбираете.</div>
          <label for="catalogPass">Пароль</label>
          <input id="catalogPass" type="password" placeholder="Пароль администратора">
          <div style="display:grid;grid-template-columns:1fr;gap:8px;margin-top:10px">
            <input id="catalogIesFile" type="file" accept=".ies">
            <input id="catalogIesPhoto" type="file" accept="image/*">
            <button class="secondary" onclick="adminAddLibraryIes()">Добавить IES в каталог</button>
          </div>
          <div style="height:10px"></div>
          <div class="muted" style="margin:0 0 8px">Удаление</div>
          <input id="catalogIesDeletePath" placeholder="Имя файла, например MAGISTRAL.ies">
          <button class="secondary" onclick="adminDeleteLibraryIes()">Удалить из каталога</button>
        </details>
      </div>
    </details>
    -->
    <div style="display:none" aria-hidden="true">
      <div id="iesStatusBox"></div>
      <div id="iesPreviewRow"></div>
      <div id="iesName"></div>
      <input id="iesFiles" type="file" multiple accept=".ies">
      <div id="iesPanel"><div id="iesLibrary"></div></div>
      <input id="catalogPass" type="password">
      <input id="catalogIesFile" type="file" accept=".ies">
      <input id="catalogIesPhoto" type="file" accept="image/*">
      <input id="catalogIesDeletePath">
      <div id="artifactsHint"></div>
      <div id="artifactsLinks"></div>
      <button id="downloadZipBtn" style="display:none"></button>
    </div>
  </section>

  <section class="result-zone empty" id="resultZone">
    <h2>Результат</h2>
    <div class="muted" id="statusText">Результат появится здесь после генерации</div>
    <div class="result-stage" id="resultStage">
      <div class="gen-overlay" id="genOverlay">
        <div class="box">
          <div class="spinner"></div>
          <div class="title">Идёт генерация</div>
          <div class="text" id="genOverlayText">Отправляем запрос в AI. Обычно 20–60 секунд.</div>
        </div>
      </div>
      <img id="finalImg" alt="">
      <canvas id="editMarkupCanvas" class="result-markup-canvas hidden" aria-hidden="true"></canvas>
    </div>
    <div class="render-history-panel hidden" id="renderHistoryPanel">
      <div class="render-history-head">История генераций в этом проекте</div>
      <div class="render-history-strip" id="renderHistoryStrip"></div>
    </div>
    <div class="tool-row result-actions-row">
      <button class="secondary" onclick="regenerate()" id="regenerateBtn" style="display:none">Перегенерировать</button>
      <button class="secondary" onclick="downloadFinal()">Скачать</button>
      <button type="button" class="help-btn-promo result-edit-btn" id="editModeToggleBtn" onclick="toggleEditMode()" disabled title="Сначала дождитесь результата">Доработать результат</button>
    </div>
    <div class="render-used-block hidden" id="renderUsedBlock" aria-hidden="true" style="display:none">
      <div class="item" id="renderScenarioInfo"></div>
      <div class="render-ies-section hidden" id="renderIesSection"><div class="render-ies-list" id="iesUsedList"></div></div>
      <p class="render-ies-empty hidden" id="renderIesEmpty"></p>
    </div>
    <div class="render-audit hidden" id="renderAudit"></div>
    <div class="edit-section collapsed" id="editSection">
      <p class="muted" id="editBtnHint" style="margin:0 0 8px">После генерации можно открыть доработку и разметить области прямо на фото.</p>
      <div class="edit-tools" id="editToolsPanel">
        <div class="edit-markup-toolbar" id="editMarkupPanel">
          <button type="button" class="secondary active" id="editBrushBtn" onclick="setEditTool('brush')">Кисть</button>
          <button type="button" class="secondary" id="editEraserBtn" onclick="setEditTool('eraser')">Ластик</button>
          <label class="brush-size">Толщина <input type="range" id="editBrushSize" min="4" max="48" value="14" oninput="updateEditBrushSize(this.value)"></label>
          <button type="button" class="secondary" onclick="clearEditMarkup()">Очистить разметку</button>
        </div>
        <p class="edit-markup-hint">Рисуйте красным прямо на результате выше. Инструкция + разметка уйдут в AI.</p>
        <textarea id="editInstruction">Убери отмеченную область и сохрани архитектуру здания.</textarea>
        <div class="tool-row" style="margin-top:12px">
          <button type="button" id="dealerEditBtn" onclick="editRender()" disabled title="Сначала дождитесь результата генерации">Отправить доработку</button>
          <button type="button" class="secondary" onclick="toggleEditMode(false)">Скрыть</button>
        </div>
      </div>
    </div>
    <div class="contact-cta-panel hidden" id="contactCtaPanel">
      <h3>Нужна более детальная визуализация?</h3>
      <p class="lead">Более детальная проработка подсветки под ваш объект:</p>
      <a class="contact-phone-btn contact-phone-btn--inline" href="tel:{{CONTACT_PHONE_TEL}}">Позвонить {{CONTACT_PHONE}}</a>
    </div>
  </section>

  <section class="feedback-zone hidden" id="feedbackZone">
    <h2 id="feedbackTitle">Обратная связь</h2>
    <p class="lead muted" id="feedbackLead">Нравится результат или нет? Оценка поможет улучшить сервис.</p>
    <div class="feedback-votes" id="feedbackVotes" role="group" aria-label="Нравится или не нравится">
      <button type="button" class="like" id="feedbackLikeBtn" onclick="setFeedbackVote('like')">Нравится</button>
      <button type="button" class="dislike" id="feedbackDislikeBtn" onclick="setFeedbackVote('dislike')">Не нравится</button>
    </div>
    <select id="feedbackIssue" aria-label="Что нужно улучшить">
      <option value="">Что нужно улучшить (необязательно)</option>
      <option value="placement_incorrect">Расстановка светильников</option>
      <option value="coverage_incomplete">Освещена не вся нужная часть фасада</option>
      <option value="overlit">Слишком ярко или есть засветка</option>
      <option value="underlit">Недостаточно света</option>
      <option value="style_mismatch">Не подходит стиль освещения</option>
      <option value="other">Другое</option>
    </select>
    <textarea id="feedbackComment" placeholder="Комментарий (необязательно)"></textarea>
    <input id="feedbackContact" type="text" placeholder="Email или телефон (необязательно)">
    <button type="button" onclick="submitFeedback()" id="feedbackSubmitBtn">Отправить отзыв</button>
    <div class="feedback-status muted" id="feedbackStatus"></div>
  </section>
  <div class="feedback-toast hidden" id="feedbackToast" role="dialog" aria-label="Оценка результата">
    <button type="button" class="feedback-toast-close" onclick="dismissFeedbackToast()" aria-label="Закрыть">×</button>
    <p class="feedback-toast-title">Как вам результат?</p>
    <p class="feedback-toast-lead muted">Краткая оценка поможет улучшить сервис.</p>
    <div class="feedback-toast-actions">
      <button type="button" class="like" onclick="quickFeedbackFromToast('like')">Нравится</button>
      <button type="button" class="dislike" onclick="quickFeedbackFromToast('dislike')">Не нравится</button>
      <button type="button" class="secondary" onclick="dismissFeedbackToast()">Позже</button>
    </div>
  </div>
</main>
<script>
let projectId = null;
let editDrawing = false;
let editLastPoint = null;
let editTool = 'brush';
let editBrushSize = 14;
let editMarkupReady = false;
let editModeOpen = false;
let historyPreviewUrl = '';
let currentFinalUrl = '';
let promptSaveTimer = null;
let dealerScenarios = [];
let routeraiModels = [];
let isGenerating = false;
let renderLimitBlocked = false;
const ROUTERAI_CLIENT_ALIASES = {
  'openai/gpt-5.5': 'openai/gpt-5-image',
};
let dealerScenarioCategories = [];
let selectedDealerScenarioId = null;
let dealerLegacyRefs = [];
let selectedLegacyRefId = null;
let contactCtaAutoScrolled = false;
let imageUploadBusy = false;
let dealerWorkMode = 'manual'; // авто-режим временно отключён
// let dealerWorkMode = localStorage.getItem('niteos_dealer_work_mode') || 'manual';
let autoScenarioBusy = false;
let feedbackVote = '';
let feedbackTimer = null;
let feedbackPromptedHistoryId = '';
let feedbackToastDismissedFor = '';
const FEEDBACK_TOAST_DELAY_MS = 60000;
const setStatus = (t) => { document.getElementById('statusText').textContent = t; };
function setFeedbackVote(vote){
  feedbackVote = (vote === 'like' || vote === 'dislike') ? vote : '';
  const likeBtn = document.getElementById('feedbackLikeBtn');
  const dislikeBtn = document.getElementById('feedbackDislikeBtn');
  if(likeBtn) likeBtn.classList.toggle('active', feedbackVote === 'like');
  if(dislikeBtn) dislikeBtn.classList.toggle('active', feedbackVote === 'dislike');
}
async function submitFeedback(){
  const statusEl = document.getElementById('feedbackStatus');
  const btn = document.getElementById('feedbackSubmitBtn');
  if(statusEl) statusEl.textContent = '';
  if(!feedbackVote){
    if(statusEl) statusEl.textContent = 'Выберите: нравится или не нравится.';
    return;
  }
  try{
    await ensureProject();
    const fd = new FormData();
    fd.append('vote', feedbackVote);
    fd.append('rating', feedbackVote === 'like' ? '5' : '1');
    fd.append('issue_type', (document.getElementById('feedbackIssue') || {}).value || '');
    fd.append('comment', (document.getElementById('feedbackComment') || {}).value || '');
    fd.append('contact', (document.getElementById('feedbackContact') || {}).value || '');
    await api(`/api/projects/${projectId}/feedback`, {method:'POST', body:fd});
    if(statusEl) statusEl.textContent = 'Спасибо! Оценка сохранена.';
    if(btn) btn.disabled = true;
    dismissFeedbackToast();
    await refresh();
  }catch(err){
    if(statusEl) statusEl.textContent = 'Не удалось отправить: ' + (err.message || err);
  }
}
function hideFeedbackToast(){
  const toast = document.getElementById('feedbackToast');
  if(toast) toast.classList.add('hidden');
}
function showFeedbackToast(){
  const toast = document.getElementById('feedbackToast');
  if(!toast) return;
  if(feedbackToastDismissedFor && feedbackToastDismissedFor === feedbackPromptedHistoryId) return;
  toast.classList.remove('hidden');
}
function dismissFeedbackToast(){
  hideFeedbackToast();
  if(feedbackPromptedHistoryId) feedbackToastDismissedFor = feedbackPromptedHistoryId;
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
}
async function quickFeedbackFromToast(vote){
  setFeedbackVote(vote);
  dismissFeedbackToast();
  await submitFeedback();
}
function scheduleFeedbackPrompt(state){
  const zone = document.getElementById('feedbackZone');
  if(!zone) return;
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  if(!state || !state.has_final){
    zone.classList.add('hidden');
    hideFeedbackToast();
    feedbackPromptedHistoryId = '';
    feedbackToastDismissedFor = '';
    return;
  }
  zone.classList.remove('hidden');
  zone.classList.remove('required');
  const title = document.getElementById('feedbackTitle');
  const lead = document.getElementById('feedbackLead');
  if(title) title.textContent = 'Обратная связь';
  if(lead) lead.textContent = 'Нравится результат или нет? Оценка поможет улучшить сервис.';
  if(!state.feedback_required){
    hideFeedbackToast();
    return;
  }
  const history = state.last_history_entry || {};
  const renderId = String(history.id || state.updated_at || 'current');
  const isNew = feedbackPromptedHistoryId !== renderId;
  if(isNew){
    feedbackVote = '';
    setFeedbackVote('');
    feedbackToastDismissedFor = '';
    const issue = document.getElementById('feedbackIssue');
    const comment = document.getElementById('feedbackComment');
    const contact = document.getElementById('feedbackContact');
    const statusEl = document.getElementById('feedbackStatus');
    if(issue) issue.value = '';
    if(comment) comment.value = '';
    if(contact) contact.value = '';
    if(statusEl) statusEl.textContent = '';
    feedbackPromptedHistoryId = renderId;
    const btn = document.getElementById('feedbackSubmitBtn');
    if(btn) btn.disabled = false;
    hideFeedbackToast();
  }
  if(feedbackToastDismissedFor === renderId) return;
  feedbackTimer = setTimeout(() => {
    if(!lastProjectState || !lastProjectState.feedback_required) return;
    if(feedbackPromptedHistoryId !== renderId) return;
    if(feedbackToastDismissedFor === renderId) return;
    showFeedbackToast();
  }, FEEDBACK_TOAST_DELAY_MS);
}
function scrollToCard(cardId){
  const el = document.getElementById(cardId);
  if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
}
function isElementMostlyInView(el){
  if(!el) return false;
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight || 1;
  const visibleTop = Math.max(0, Math.min(vh, r.bottom) - Math.max(0, r.top));
  const ratio = visibleTop / Math.max(1, r.height);
  return ratio >= 0.55;
}
function nudgeToCard(cardId){
  const el = document.getElementById(cardId);
  if(!el) return;
  if(isTextField(document.activeElement)) return;
  if(isElementMostlyInView(el)) return;
  el.classList.add('next-step');
  el.scrollIntoView({behavior:'smooth', block:'start'});
  setTimeout(()=> el.classList.remove('next-step'), 1600);
}
function shouldAutoScrollToResult(){
  const resultZone = document.getElementById('resultZone');
  if(!resultZone) return false;
  const active = document.activeElement;
  if(active && (active.id === 'editInstruction' || active.closest('#editSection'))) return false;
  if(isElementMostlyInView(resultZone)) return false;
  return true;
}
function autoScrollToResult(){
  if(!shouldAutoScrollToResult()) return;
  const resultZone = document.getElementById('resultZone');
  if(!resultZone) return;
  resultZone.classList.add('scroll-nudge');
  resultZone.scrollIntoView({behavior:'smooth', block:'start'});
  setTimeout(()=> resultZone.classList.remove('scroll-nudge'), 1800);
}
function clearNextStepHighlight(){
  ['sourceCard','scenariosCard','assignmentCard'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.classList.remove('next-step');
  });
}
function setWorkflow(step, done){
  const setState = (id, state) => {
    const el = document.getElementById(id);
    if(!el) return;
    el.classList.remove('active','done');
    if(state === 'done') el.classList.add('done');
    if(state === 'active') el.classList.add('active');
  };
  const hint = document.getElementById('workflowHint');
  const s1 = !!done.s1, s2 = !!done.s2, s3 = !!done.s3;
  setState('wfS1', s1 ? 'done' : (step === 1 ? 'active' : ''));
  setState('wfS2', s2 ? 'done' : (step === 2 ? 'active' : ''));
  setState('wfS3', s3 ? 'done' : (step === 3 ? 'active' : ''));
  clearNextStepHighlight();
  const nextMap = {1:'sourceCard',2:'scenariosCard',3:'assignmentCard'};
  const nextEl = document.getElementById(nextMap[step] || '');
  if(nextEl) nextEl.classList.add('next-step');
  if(!hint) return;
  if(step === 1) hint.innerHTML = 'Шаг 1: <b>вставьте</b> (Ctrl+V) или <b>загрузите</b> фото фасада.';
  else if(step === 2) hint.innerHTML = 'Шаг 2: выберите <b>сценарий</b> (рекомендуется) — подставит эталон, IES и задание.';
  else if(step === 3) hint.innerHTML = 'Шаг 3: уточните <b>задание</b> и нажмите <b>Начать генерацию</b>.';
}
function updateWorkflowFromProject(p){
  const hasSource = !!p.has_source;
  const hasScenarioOrTemplate = !!(p.dealer_scenario_id || p.dealer_legacy_ref || p.has_style);
  const hasPrompt = !!(p.prompt_preview && String(p.prompt_preview).trim().length > 0);
  const hasFinal = !!p.has_final;
  const done = { s1: hasSource, s2: hasScenarioOrTemplate, s3: hasPrompt };
  if(hasFinal){
    const hint = document.getElementById('workflowHint');
    if(hint) hint.innerHTML = 'Готово: можно <b>Перегенерировать</b>, <b>Скачать</b> или <b>Доработать результат</b>.';
    ['wfS1','wfS2','wfS3'].forEach(id => { const el = document.getElementById(id); if(el) el.classList.add('done'); });
    clearNextStepHighlight();
    return;
  }
  let next = 1;
  if(!hasSource) next = 1;
  else if(!hasScenarioOrTemplate) next = 2;
  else next = 3;
  setWorkflow(next, done);
}
function showContactCta(openModal){
  const panel = document.getElementById('contactCtaPanel');
  const modal = document.getElementById('contactCtaModal');
  if(panel) panel.classList.remove('hidden');
  if(openModal && modal){
    modal.classList.add('open');
    contactCtaAutoScrolled = true;
  } else if(panel && !contactCtaAutoScrolled){
    contactCtaAutoScrolled = true;
    setTimeout(() => panel.scrollIntoView({behavior:'smooth', block:'nearest'}), 450);
  }
}
function closeContactCtaModal(){
  const modal = document.getElementById('contactCtaModal');
  if(modal) modal.classList.remove('open');
  const panel = document.getElementById('contactCtaPanel');
  if(panel) setTimeout(() => panel.scrollIntoView({behavior:'smooth', block:'nearest'}), 200);
}
function hideContactCta(){
  const panel = document.getElementById('contactCtaPanel');
  const modal = document.getElementById('contactCtaModal');
  if(panel) panel.classList.add('hidden');
  if(modal) modal.classList.remove('open');
  contactCtaAutoScrolled = false;
}
let helpStepIndex = 0;
let tourActiveTarget = null;
let tourFocusEl = null;
let tourRepositionTimer = null;
let guidedTourMode = false;
let guidedGenerateClicked = false;
let lastProjectState = null;
let guidedAutoAdvanceTimer = null;
const TOUR_CARD_RESERVE = 412;
function setTourDim(el, top, left, width, height){
  if(!el) return;
  if(width <= 0 || height <= 0){ el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.style.top = top + 'px';
  el.style.left = left + 'px';
  el.style.width = width + 'px';
  el.style.height = height + 'px';
}
function hideTourDims(){
  ['tourDimTop','tourDimLeft','tourDimBottom','tourDimGap'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  });
}
function hideWelcomeDims(){
  ['welcomeDimTop','welcomeDimLeft','welcomeDimBottom','welcomeDimGap'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  });
}
function positionSpotlightOn(targetEl, spotlightId, dimIds, cardReserve){
  const spotlight = document.getElementById(spotlightId);
  if(!targetEl || !spotlight) return;
  const pad = 8;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const contentRight = Math.max(0, vw - (cardReserve || 0));
  const rect = targetEl.getBoundingClientRect();
  const top = Math.max(0, rect.top - pad);
  const left = Math.max(0, rect.left - pad);
  const bottom = Math.min(vh, rect.bottom + pad);
  const right = Math.min(contentRight, rect.right + pad);
  const width = Math.max(0, right - left);
  const height = Math.max(0, bottom - top);
  spotlight.style.display = width > 0 && height > 0 ? 'block' : 'none';
  spotlight.style.left = left + 'px';
  spotlight.style.top = top + 'px';
  spotlight.style.width = width + 'px';
  spotlight.style.height = height + 'px';
  const [topId, leftId, bottomId, gapId] = dimIds;
  setTourDim(document.getElementById(topId), 0, 0, contentRight, top);
  setTourDim(document.getElementById(leftId), top, 0, left, height);
  setTourDim(document.getElementById(bottomId), bottom, 0, contentRight, vh - bottom);
  setTourDim(document.getElementById(gapId), top, right, contentRight - right, height);
}
function positionTourUi(){
  const step = TOUR_STEPS[helpStepIndex];
  const targetEl = document.querySelector(step.focus || step.target);
  positionSpotlightOn(targetEl, 'tourSpotlight', ['tourDimTop','tourDimLeft','tourDimBottom','tourDimGap'], TOUR_CARD_RESERVE);
}
function isWelcomeFromLanding(){
  try{
    return new URLSearchParams(location.search).get('welcome') === '1'
      || sessionStorage.getItem('niteos_from_landing') === '1';
  }catch(_){
    return new URLSearchParams(location.search).get('welcome') === '1';
  }
}
function positionWelcomeTourUi(){
  const btn = document.getElementById('helpBtnPromo');
  const card = document.getElementById('welcomeTourCard');
  if(card){
    card.style.top = '50%';
    card.style.left = '50%';
    card.style.transform = 'translate(-50%,-50%)';
  }
  if(btn){
    btn.classList.add('tour-focus-pulse');
    positionSpotlightOn(btn, 'welcomeSpotlight', ['welcomeDimTop','welcomeDimLeft','welcomeDimBottom','welcomeDimGap'], 0);
  } else {
    hideWelcomeDims();
    const spotlight = document.getElementById('welcomeSpotlight');
    if(spotlight) spotlight.style.display = 'none';
  }
}
function showWelcomeTourPrompt(forceFromLanding){
  const fromLanding = forceFromLanding || isWelcomeFromLanding();
  if(!fromLanding) return;
  const root = document.getElementById('welcomeTourRoot');
  if(!root) return;
  root.classList.add('open');
  positionWelcomeTourUi();
  setTimeout(positionWelcomeTourUi, 200);
  setTimeout(positionWelcomeTourUi, 700);
}
function dismissWelcomeTourPrompt(){
  const root = document.getElementById('welcomeTourRoot');
  if(root) root.classList.remove('open');
  const btn = document.getElementById('helpBtnPromo');
  if(btn) btn.classList.remove('tour-focus-pulse');
  hideWelcomeDims();
  const spotlight = document.getElementById('welcomeSpotlight');
  if(spotlight) spotlight.style.display = 'none';
  try{
    const clean = new URL(location.href);
    clean.searchParams.delete('welcome');
    history.replaceState({}, '', clean.pathname + clean.search + clean.hash);
  }catch(_){}
}
function initWelcomeFromLanding(){
  if(!isWelcomeFromLanding()) return;
  try{ sessionStorage.removeItem('niteos_from_landing'); }catch(_){}
  const run = () => showWelcomeTourPrompt(true);
  setTimeout(run, 500);
  setTimeout(run, 1100);
}
const TOUR_STEPS = [
  {
    id: 'photo',
    target: '#sourceCard',
    focus: '#sourceUploadBtn',
    badge: '1',
    title: 'Шаг 1 — Фото фасада',
    lead: 'Загрузите дневное фото здания. Архитектуру AI не меняет — только добавляет ночную подсветку.',
    waitHint: 'Загрузите фото (кнопка <b>Загрузить</b>, Ctrl+V или перетащите) — дальше откроется шаг 2.',
    actions: [
      'Нажмите <b>Загрузить</b> и выберите файл',
      'Или кликните в превью и вставьте через <b>Ctrl+V</b>',
      'Можно взять фото из <b>Каталога</b>'
    ]
  },
  {
    id: 'scenario',
    target: '#scenariosCard',
    focus: '#dealerScenarioGrid .scenario-card',
    badge: '2',
    title: 'Шаг 2 — Сценарий',
    lead: 'Выберите сценарий вручную — подставятся эталон света, IES и текст задания.',
    waitHint: 'Нажмите на любой <b>сценарий</b> в ленте — перейдём к шагу 3.',
    actions: [
      'Прокрутите карточки и выберите <b>сценарий</b>',
      'Сценарий подставит эталон + IES + задание',
      'При желании можно заменить эталон кнопкой <b>Свой эталон</b>'
    ]
  },
  {
    id: 'generate',
    target: '#assignmentCard',
    focus: '#generateBtn',
    badge: '3',
    title: 'Шаг 3 — Генерация',
    lead: 'Проверьте задание, при необходимости выберите модель (по умолчанию Nano Banana Gemini 3.1 preview) и запустите рендер.',
    waitHint: 'Нажмите <b>Начать генерацию</b> — дождёмся результата на шаге 4.',
    actions: [
      'Проверьте или поправьте текст задания',
      'Выберите <b>модель</b> — у каждой указано типичное время',
      'Нажмите <b>Начать генерацию</b>'
    ]
  },
  {
    id: 'result',
    target: '#resultZone',
    focus: '#resultStage',
    badge: '4',
    title: 'Шаг 4 — Результат',
    lead: 'Здесь появится ночной рендер с водяным знаком. Можно скачать или открыть доработку поверх фото.',
    waitHint: 'Дождитесь окончания генерации — картинка появится в этом блоке.',
    actions: [
      'Нажмите <b>Скачать</b>, чтобы сохранить PNG',
      'При необходимости — <b>Доработать результат</b> (разметка прямо на финале)',
      'История версий — миниатюры под результатом (с моделью)'
    ]
  },
  {
    id: 'feedback',
    target: '#feedbackZone',
    focus: '#feedbackLikeBtn',
    badge: '5',
    title: 'Шаг 5 — Оценка',
    lead: 'После просмотра результата можно оценить работу — форма внизу страницы. Через минуту появится небольшое напоминание, его можно закрыть.',
    waitHint: 'Оценка необязательна — можно вернуться к ней позже.',
    actions: [
      'Форма <b>Обратная связь</b> находится ниже результата',
      'Через минуту — компактное окошко в углу экрана',
      'Можно нажать <b>Позже</b> и продолжить работу с результатом'
    ]
  }
];
function tourStepIndex(id){
  return TOUR_STEPS.findIndex(s => s.id === id);
}
function guidedStepComplete(stepIndex, p){
  if(!p) return false;
  const step = TOUR_STEPS[stepIndex];
  if(!step) return false;
  if(step.id === 'photo') return !!p.has_source;
  if(step.id === 'scenario') return !!(p.dealer_scenario_id || p.dealer_legacy_ref);
  if(step.id === 'generate') return !!guidedGenerateClicked;
  if(step.id === 'result') return !!p.has_final;
  if(step.id === 'feedback') return !!p.has_final;
  return false;
}
function firstIncompleteGuidedStep(p){
  for(let i = 0; i < TOUR_STEPS.length; i++){
    if(!guidedStepComplete(i, p)) return i;
  }
  return TOUR_STEPS.length - 1;
}
function clearTourPulse(){
  if(tourFocusEl){
    tourFocusEl.classList.remove('tour-focus-pulse');
    tourFocusEl = null;
  }
}
function tourActionsHtml(actions){
  if(!actions || !actions.length) return '';
  return `<div class="tour-actions"><div class="label">Куда нажимать</div><ul>${
    actions.map(a => `<li>${a}</li>`).join('')
  }</ul></div>`;
}
function clearTourHighlight(){
  if(tourActiveTarget){
    tourActiveTarget.classList.remove('tour-target-active');
    tourActiveTarget = null;
  }
  clearTourPulse();
}
function renderHelpStep(){
  const step = TOUR_STEPS[helpStepIndex];
  const total = TOUR_STEPS.length;
  const targetEl = document.querySelector(step.target);
  const focusEl = document.querySelector(step.focus || step.target);
  const complete = guidedTourMode && guidedStepComplete(helpStepIndex, lastProjectState);
  document.getElementById('helpStepBadge').textContent = step.badge;
  document.getElementById('helpTitle').textContent = step.title;
  document.getElementById('helpStepCounter').textContent = guidedTourMode
    ? `Интерактивный тур · шаг ${helpStepIndex + 1} из ${total}`
    : `Шаг ${helpStepIndex + 1} из ${total}`;
  const waitHtml = guidedTourMode && !complete && step.waitHint
    ? `<p class="tour-wait-hint">${step.waitHint}</p>` : '';
  document.getElementById('helpBody').innerHTML =
    `<p class="help-lead">${step.lead}</p>${tourActionsHtml(step.actions)}${waitHtml}`;
  document.getElementById('helpDots').innerHTML = TOUR_STEPS.map((_, i) =>
    `<span class="help-dot${i === helpStepIndex ? ' active' : ''}${guidedTourMode ? ' locked' : ''}" title="Шаг ${i + 1}"></span>`
  ).join('');
  const prevBtn = document.getElementById('helpPrevBtn');
  const nextBtn = document.getElementById('helpNextBtn');
  const skipBtn = document.querySelector('.tour-skip');
  if(prevBtn) prevBtn.disabled = guidedTourMode || helpStepIndex === 0;
  if(skipBtn) skipBtn.textContent = guidedTourMode ? 'Выйти из тура' : 'Пропустить';
  if(nextBtn){
    if(guidedTourMode){
      const genIdx = tourStepIndex('generate');
      if(helpStepIndex === TOUR_STEPS.length - 1){
        nextBtn.textContent = complete ? 'Готово ✓' : 'Посмотрите результат…';
        nextBtn.disabled = !complete;
      } else if(helpStepIndex === genIdx){
        nextBtn.textContent = 'Нажмите «Начать генерацию»';
        nextBtn.disabled = true;
      } else {
        nextBtn.textContent = complete ? 'Далее →' : 'Ждём действие…';
        nextBtn.disabled = !complete;
      }
    } else {
      nextBtn.disabled = false;
      nextBtn.textContent = helpStepIndex === total - 1 ? 'Понятно ✓' : 'Далее →';
    }
  }
  clearTourHighlight();
  clearTourPulse();
  if(targetEl){
    tourActiveTarget = targetEl;
    targetEl.classList.add('tour-target-active');
    targetEl.scrollIntoView({behavior:'smooth', block:'center'});
  }
  if(focusEl && guidedTourMode){
    tourFocusEl = focusEl;
    focusEl.classList.add('tour-focus-pulse');
  }
  clearTimeout(tourRepositionTimer);
  tourRepositionTimer = setTimeout(positionTourUi, 420);
  setTimeout(positionTourUi, 700);
}
function openGuidedTour(){
  dismissWelcomeTourPrompt();
  guidedTourMode = true;
  guidedGenerateClicked = false;
  helpStepIndex = firstIncompleteGuidedStep(lastProjectState || {});
  document.getElementById('tourRoot').classList.add('open');
  document.getElementById('tourCard').classList.add('open');
  renderHelpStep();
}
function openHelp(){ openGuidedTour(); }
function closeHelp(){
  guidedTourMode = false;
  guidedGenerateClicked = false;
  clearTimeout(guidedAutoAdvanceTimer);
  document.getElementById('tourRoot').classList.remove('open');
  document.getElementById('tourCard').classList.remove('open');
  document.getElementById('tourSpotlight').style.display = 'none';
  hideTourDims();
  clearTourHighlight();
  clearTimeout(tourRepositionTimer);
  try{ localStorage.setItem('niteos_tour_seen', '1'); }catch(_){}
}
function prevHelpStep(){
  if(guidedTourMode) return;
  if(helpStepIndex > 0){ helpStepIndex--; renderHelpStep(); }
}
function nextHelpStep(){
  if(helpStepIndex < TOUR_STEPS.length - 1){ helpStepIndex++; renderHelpStep(); }
}
function helpNextAction(){
  if(guidedTourMode){
    if(!guidedStepComplete(helpStepIndex, lastProjectState)) return;
    if(helpStepIndex >= TOUR_STEPS.length - 1){ closeHelp(); return; }
    if(TOUR_STEPS[helpStepIndex]?.id === 'generate') return;
    nextHelpStep();
    return;
  }
  if(helpStepIndex >= TOUR_STEPS.length - 1) closeHelp();
  else nextHelpStep();
}
function goHelpStep(index){
  if(guidedTourMode) return;
  if(index < 0 || index >= TOUR_STEPS.length) return;
  helpStepIndex = index;
  renderHelpStep();
}
function checkGuidedTourAdvance(p){
  if(!guidedTourMode || !p) return;
  lastProjectState = p;
  renderHelpStep();
  if(!guidedStepComplete(helpStepIndex, p)) return;
  if(helpStepIndex >= TOUR_STEPS.length - 1) return;
  if(TOUR_STEPS[helpStepIndex]?.id === 'generate') return;
  clearTimeout(guidedAutoAdvanceTimer);
  guidedAutoAdvanceTimer = setTimeout(() => {
    if(!guidedTourMode) return;
    if(!guidedStepComplete(helpStepIndex, p)) return;
    if(helpStepIndex >= TOUR_STEPS.length - 1) return;
    if(TOUR_STEPS[helpStepIndex]?.id === 'generate') return;
    helpStepIndex++;
    renderHelpStep();
  }, 700);
}
function onTourLayout(){
  if(document.getElementById('welcomeTourRoot')?.classList.contains('open')) positionWelcomeTourUi();
  if(!document.getElementById('tourRoot').classList.contains('open')) return;
  positionTourUi();
}
window.addEventListener('resize', onTourLayout);
window.addEventListener('scroll', onTourLayout, true);
document.addEventListener('keydown', (e) => {
  if(document.getElementById('welcomeTourRoot')?.classList.contains('open')){
    if(e.key === 'Escape') dismissWelcomeTourPrompt();
    return;
  }
  const tour = document.getElementById('tourRoot');
  if(tour && tour.classList.contains('open')){
    if(e.key === 'Escape') closeHelp();
    if(e.key === 'ArrowRight' || e.key === 'Enter') helpNextAction();
    if(e.key === 'ArrowLeft') prevHelpStep();
    return;
  }
});
function showGenOverlay(text){
  document.getElementById('genOverlayText').textContent = text || 'Идёт генерация...';
  document.getElementById('genOverlay').classList.add('open');
}
function hideGenOverlay(){ document.getElementById('genOverlay').classList.remove('open'); }
async function api(path, opts={}) {
  const r = await fetch(path, {credentials:'same-origin', ...opts});
  if (!r.ok) {
    let msg = await r.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || msg;
      if (Array.isArray(msg)) msg = msg.map(x => x.msg || String(x)).join(', ');
    } catch(_) {}
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return await r.json();
}
async function refreshRenderLimit(){
  try {
    const s = await api('/api/visitor/limits');
    if(!s.enabled){
      renderLimitBlocked = false;
      updateGenerateControls(lastProjectState);
      return;
    }
    const el = document.getElementById('renderLimitHint');
    renderLimitBlocked = s.remaining <= 0;
    if(!el) return;
    el.classList.remove('hidden');
    if(renderLimitBlocked){
      el.textContent = `Лимит на сегодня исчерпан (${s.limit} в сутки). Для детальной визуализации позвоните {{CONTACT_PHONE}}.`;
    } else {
      el.textContent = `Осталось генераций сегодня: ${s.remaining} из ${s.limit}`;
    }
    updateGenerateControls(lastProjectState);
  } catch(_) {}
}
function normalizeRouteraiModel(modelId){
  const id = (modelId || '').trim();
  return ROUTERAI_CLIENT_ALIASES[id] || id;
}
function routeraiModelMeta(modelId){
  return routeraiModels.find(m => m.id === modelId) || null;
}
function routeraiModelLabel(modelId){
  const item = routeraiModelMeta(modelId);
  return item ? item.label : modelId;
}
function routeraiModelEta(modelId){
  const item = routeraiModelMeta(modelId);
  return (item && item.eta) ? item.eta : '';
}
function routeraiModelShort(modelId){
  const id = (modelId || '').trim();
  if(!id) return '—';
  if(id === 'niteos/finetuned-lora') return 'NITEOS LoRA';
  const tail = id.split('/').pop() || id;
  return tail.replace('gemini-', 'g').replace('flash-image-preview', '3.1 preview').replace('flash-image', 'flash');
}
function updateRouteraiModelHint(){
  const sel = document.getElementById('routeraiModel');
  const hint = document.getElementById('routeraiModelHint');
  const pill = document.getElementById('routeraiModelPill');
  if(!sel || !hint) return;
  const val = sel.value;
  if(!val){
    hint.textContent = sel.options.length <= 1 ? 'Загрузка списка моделей…' : 'Выберите модель.';
    if(pill) pill.classList.add('hidden');
    return;
  }
  const eta = routeraiModelEta(val);
  const meta = routeraiModelMeta(val) || {};
  let extra = '';
  if(val === 'niteos/finetuned-lora'){
    extra = meta.mode === 'lora_endpoint'
      ? ' Режим: Flux LoRA endpoint.'
      : ' Режим: soft few-shot (датасет), пока FINETUNED_IMAGE_API_URL не задан.';
  } else if(val.includes('gpt-5')){
    extra = ' Медленная модель: генерация может занять до 10 минут — не закрывайте страницу.';
  }
  hint.textContent = 'Будет использована: ' + routeraiModelLabel(val)
    + (eta ? ` · обычно ${eta}` : '')
    + (extra || '.');
  if(pill){
    pill.textContent = (val === 'niteos/finetuned-lora' ? 'NITEOS LoRA' : (val.split('/').pop() || val)) + (eta ? ` · ${eta}` : '');
    pill.classList.remove('hidden');
  }
}
function onRouteraiModelChange(){
  const sel = document.getElementById('routeraiModel');
  if(sel && sel.value){
    localStorage.setItem('niteos_routerai_model', sel.value);
  }
  updateRouteraiModelHint();
}
function onReviewProfileChange(){
  // Auto re-generation is disabled; kept as no-op for older saved scripts.
}
function setRouteraiModel(modelId){
  const sel = document.getElementById('routeraiModel');
  if(!sel || !modelId) return false;
  const normalized = normalizeRouteraiModel(modelId);
  if([...sel.options].some(o => o.value === normalized)){
    sel.value = normalized;
    localStorage.setItem('niteos_routerai_model', normalized);
    updateRouteraiModelHint();
    return true;
  }
  return false;
}
function updateGenerateControls(p){
  const btn = document.getElementById('generateBtn');
  const reason = document.getElementById('generateBlockReason');
  if(!btn) return;
  const state = p || lastProjectState || {};
  const hasSource = !!state.has_source;
  const promptEl = document.getElementById('prompt');
  const hasPrompt = !!((promptEl && promptEl.value.trim()) || (state.prompt || '').trim());
  let blocked = '';
  if(isGenerating){
    btn.disabled = true;
    btn.classList.add('is-busy');
  } else if(renderLimitBlocked){
    btn.disabled = true;
    blocked = 'Дневной лимит генераций исчерпан.';
  } else if(!hasSource){
    btn.disabled = true;
    blocked = 'Сначала загрузите фото фасада (шаг 1).';
  } else if(!hasPrompt){
    btn.disabled = true;
    blocked = 'Выберите сценарий или введите задание.';
  } else {
    btn.disabled = false;
    btn.classList.remove('is-busy');
  }
  if(reason){
    if(blocked && !isGenerating){
      reason.textContent = blocked;
      reason.classList.remove('hidden');
    } else {
      reason.classList.add('hidden');
    }
  }
}
async function createProject(){
  const fd = new FormData();
  fd.append('name', 'Cloud project');
  fd.append('mode', 'dealer');
  const p = await api('/api/projects', {method:'POST', body:fd});
  projectId = p.id;
  document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  const studioLink = document.getElementById('studioLink');
  if(studioLink) studioLink.href = '/studio?project=' + projectId;
  setStatus('Проект создан');
  refreshProjects();
  refresh();
}
async function toggleProjects(){
  const panel = document.getElementById('projectsPanel');
  panel.classList.toggle('open');
  if(panel.classList.contains('open')) await refreshProjects();
}
async function refreshProjects(){
  const projects = await api('/api/projects');
  const panel = document.getElementById('projectsPanel');
  if(!projects.length){
    panel.innerHTML = '<div class="muted">История пока пустая</div>';
    return;
  }
  panel.innerHTML = projects.map(projectCard).join('');
}
function esc(value){
  return String(value || '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
}
function projectCard(p){
  const status = esc(p.status || 'created');
  const updated = esc(p.updated_at || p.created_at || '');
  const prompt = esc(p.prompt_preview || 'Prompt не сохранен');
  const result = p.has_final ? 'финал есть' : 'финала нет';
  const light = p.has_light_map ? 'карта есть' : 'карты нет';
  return `<div class="project-card">
    <div class="title">${esc(p.name || 'Проект')} / ${esc(p.id)}</div>
    <div class="meta">Статус: ${status}<br>Обновлен: ${updated}<br>Фото: ${p.has_source ? 'есть' : 'нет'} · IES: ${p.ies_count || 0} · Style: ${p.has_style ? 'есть' : 'нет'}<br>${light} · ${result}<br>Задание: ${prompt}</div>
    <button class="secondary" onclick="openProject('${esc(p.id)}')">Открыть</button>
  </div>`;
}
async function openProject(id){
  const p = await api(`/api/projects/${id}`);
  projectId = id;
  document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  const studioLink = document.getElementById('studioLink');
  if(studioLink) studioLink.href = '/studio?project=' + projectId;
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  if(p.routerai_model) setRouteraiModel(p.routerai_model);
  setStatus('Проект открыт');
  refreshPipelineLog(false);
  refresh();
}
async function ensureProject(){ if(!projectId) await createProject(); }
function chooseFile(inputId){
  const input = document.getElementById(inputId);
  input.value = '';
  input.click();
}
function togglePanel(panelId){
  refreshLibrary();
  document.getElementById(panelId).classList.toggle('open');
}
function isClipboardImageItem(item){
  if(!item || item.kind !== 'file') return false;
  const type = (item.type || '').toLowerCase();
  return !type || type.startsWith('image/');
}
function imageFromClipboard(event){
  const items = event.clipboardData && event.clipboardData.items;
  if(!items) return null;
  for(const item of items){
    if(!isClipboardImageItem(item)) continue;
    const file = item.getAsFile();
    if(file && file.size > 0) return file;
  }
  return null;
}
function imageFromDataTransfer(dt){
  if(!dt) return null;
  if(dt.files && dt.files.length){
    for(const f of dt.files){
      const type = (f.type || '').toLowerCase();
      if(!type || type.startsWith('image/')) return f;
    }
  }
  if(dt.items){
    for(const item of dt.items){
      if(!isClipboardImageItem(item)) continue;
      const file = item.getAsFile();
      if(file && file.size > 0) return file;
    }
  }
  return null;
}
function namedImageFile(file, prefix){
  const name = (file.name || '').trim();
  if(name && name !== 'image.png' && name !== 'blob') return file;
  const ext = ((file.type || 'image/png').split('/')[1] || 'png').replace('jpeg', 'jpg');
  return new File([file], `${prefix}-${Date.now()}.${ext}`, {type: file.type || 'image/png'});
}
async function uploadSource(file){
  if(imageUploadBusy) return;
  await ensureProject();
  const f = file || document.getElementById('sourceFile').files[0];
  if(!f) return;
  imageUploadBusy = true;
  try{
    const fd = new FormData();
    fd.append('file', namedImageFile(f, 'pasted-source'));
    await api(`/api/projects/${projectId}/source`, {method:'POST', body:fd});
    setStatus('Фото загружено и сохранено в каталог');
    refresh();
    setTimeout(()=> nudgeToCard('scenariosCard'), 250);
    if(false && dealerWorkMode === 'auto'){
      setTimeout(()=> runAutoScenario({silentStart:true}), 400);
    }
  }catch(err){
    setStatus('Ошибка загрузки фото: ' + err.message);
  }finally{
    imageUploadBusy = false;
  }
}
function setDealerWorkMode(mode){
  // Авто временно отключён — всегда manual
  dealerWorkMode = 'manual';
  // dealerWorkMode = (mode === 'auto') ? 'auto' : 'manual';
  localStorage.setItem('niteos_dealer_work_mode', 'manual');
  const manualBtn = document.getElementById('workModeManualBtn');
  const autoBtn = document.getElementById('workModeAutoBtn');
  const autoPanel = document.getElementById('autoScenarioPanel');
  const manualPanel = document.getElementById('manualScenarioPanel');
  if(manualBtn) manualBtn.classList.toggle('active', true);
  if(autoBtn) autoBtn.classList.toggle('active', false);
  if(autoPanel) autoPanel.classList.add('hidden');
  if(manualPanel) manualPanel.classList.remove('hidden');
  const wf = document.querySelector('#wfS2 span:last-child');
  if(wf) wf.textContent = 'Сценарий / шаблон';
  // if(dealerWorkMode === 'auto') loadAutoTestPhotos();
}
async function loadAutoTestPhotos(){
  const strip = document.getElementById('autoTestPhotoStrip');
  if(!strip) return;
  try{
    const data = await api('/api/auto-test-photos');
    const items = data.items || [];
    if(!items.length){
      strip.innerHTML = '<div class="muted">Эталоны не найдены в assets/viz_examples/examples</div>';
      return;
    }
    strip.innerHTML = items.map(item => `
      <div class="auto-test-card" data-file="${esc(item.filename)}" onclick="selectAutoTestPhoto('${esc(item.filename)}')">
        <img src="${esc(item.preview_url)}" alt="${esc(item.filename)}" loading="lazy">
        <div class="title">${esc(item.filename)}</div>
      </div>
    `).join('');
  }catch(err){
    strip.innerHTML = `<div class="muted">Не удалось загрузить набор: ${esc(err.message || err)}</div>`;
  }
}
function applyAutoScenarioResult(data){
  const statusEl = document.getElementById('autoScenarioStatus');
  const promptEl = document.getElementById('prompt');
  const previewEl = document.getElementById('autoPromptPreview');
  selectedDealerScenarioId = null;
  selectedLegacyRefId = null;
  if(data.base_prompt && promptEl){
    promptEl.value = data.base_prompt;
    schedulePromptSave();
  }
  const conf = (typeof data.confidence === 'number') ? ` · уверенность ${Math.round(data.confidence * 100)}%` : '';
  const fallback = data.fallback ? ' · fallback' : '';
  const label = data.viz_filename || data.scenario_name || 'эталон виз';
  if(statusEl){
    statusEl.textContent = data.generated
      ? `Готово: ${label}${conf}${fallback}. ${(data.reason || '').trim()}`
      : `Эталон: ${label}${conf}${fallback}. ${(data.reason || '').trim()}`;
  }
  const scenStatus = document.getElementById('dealerScenarioStatus');
  if(scenStatus) scenStatus.textContent = `Авто-эталон: ${label}`;
  if(previewEl) previewEl.textContent = data.render_prompt || data.base_prompt || 'Промпт пуст';
  const details = document.getElementById('autoPromptDetails');
  if(details) details.open = !data.generated;
}
async function selectAutoTestPhoto(filename){
  await ensureProject();
  if(autoScenarioBusy) return;
  if(!(lastProjectState && lastProjectState.has_source)){
    setStatus('Сначала загрузите своё фото фасада в шаге 1');
    const statusEl = document.getElementById('autoScenarioStatus');
    if(statusEl) statusEl.textContent = 'Нужно своё фото фасада — эталоны только для переноса света.';
    nudgeToCard('sourceCard');
    return;
  }
  autoScenarioBusy = true;
  document.querySelectorAll('#autoTestPhotoStrip .auto-test-card').forEach(card => {
    card.classList.toggle('selected', card.getAttribute('data-file') === filename);
  });
  const statusEl = document.getElementById('autoScenarioStatus');
  const btn = document.getElementById('autoScenarioBtn');
  if(btn){ btn.disabled = true; btn.textContent = 'Генерация…'; }
  if(statusEl) statusEl.textContent = `Эталон ${filename}: перенос света и генерация…`;
  setStatus('Авто: эталон + генерация…');
  showGenOverlay('Авто-режим: перенос света с эталона и генерация финала...');
  try{
    const fd = new FormData();
    fd.append('filename', filename);
    fd.append('run_auto', '1');
    fd.append('generate', '1');
    const modelSel = document.getElementById('routeraiModel');
    if(modelSel && modelSel.value) fd.append('routerai_model', modelSel.value);
    const data = await api(`/api/projects/${projectId}/auto-test-load`, {method:'POST', body:fd});
    if(data.auto) applyAutoScenarioResult(data.auto);
    setStatus(data.auto && data.auto.generated ? 'Авто-рендер готов' : 'Авто-эталон применён');
    await refresh();
    setTimeout(()=> {
      const zone = document.getElementById('resultZone');
      if(zone) zone.scrollIntoView({behavior:'smooth', block:'start'});
    }, 300);
  }catch(err){
    if(statusEl) statusEl.textContent = 'Ошибка авто: ' + (err.message || err);
    setStatus('Ошибка авто: ' + (err.message || err));
  }finally{
    autoScenarioBusy = false;
    hideGenOverlay();
    if(btn){ btn.disabled = false; btn.textContent = 'Авто: выбрать эталон и сгенерировать'; }
    updateGenerateControls(lastProjectState);
  }
}
async function runAutoScenario(opts){
  opts = opts || {};
  await ensureProject();
  if(autoScenarioBusy) return;
  if(!(lastProjectState && lastProjectState.has_source)){
    setStatus('Сначала загрузите фото фасада');
    const statusEl = document.getElementById('autoScenarioStatus');
    if(statusEl) statusEl.textContent = 'Нужно фото фасада в шаге 1.';
    return;
  }
  const statusEl = document.getElementById('autoScenarioStatus');
  const btn = document.getElementById('autoScenarioBtn');
  autoScenarioBusy = true;
  if(btn){ btn.disabled = true; btn.textContent = 'Подбор + генерация…'; }
  if(statusEl) statusEl.textContent = opts.silentStart
    ? 'Фото получено — AI выбирает эталон из 20 и генерирует…'
    : 'AI выбирает лучший эталон света из 20 и генерирует…';
  setStatus('Авто-режим: эталон виз → генерация…');
  showGenOverlay('Авто-режим: выбор эталона из 20 и генерация финала...');
  try{
    const fd = new FormData();
    const modelSel = document.getElementById('routeraiModel');
    if(modelSel && modelSel.value) fd.append('routerai_model', modelSel.value);
    fd.append('generate', '1');
    const data = await api(`/api/projects/${projectId}/auto-scenario`, {method:'POST', body:fd});
    applyAutoScenarioResult(data);
    if(data.viz_filename){
      document.querySelectorAll('#autoTestPhotoStrip .auto-test-card').forEach(card => {
        card.classList.toggle('selected', card.getAttribute('data-file') === data.viz_filename);
      });
    }
    setStatus(data.generated ? 'Авто-рендер готов' : 'Авто-эталон выбран');
    await refresh();
    setTimeout(()=> {
      const zone = document.getElementById('resultZone');
      if(zone) zone.scrollIntoView({behavior:'smooth', block:'start'});
    }, 300);
  }catch(err){
    if(statusEl) statusEl.textContent = 'Не удалось выполнить авто: ' + (err.message || err);
    setStatus('Ошибка авто: ' + (err.message || err));
  }finally{
    autoScenarioBusy = false;
    hideGenOverlay();
    if(btn){ btn.disabled = false; btn.textContent = 'Авто: выбрать эталон и сгенерировать'; }
    updateGenerateControls(lastProjectState);
  }
}
async function uploadIes(){
  await ensureProject();
  const fd = new FormData(); for(const f of document.getElementById('iesFiles').files) fd.append('files', f);
  await api(`/api/projects/${projectId}/ies`, {method:'POST', body:fd}); setStatus('IES загружены и сохранены в каталог'); refresh();
  setTimeout(()=> nudgeToCard('scenariosCard'), 250);
}
async function uploadStyle(file){
  if(imageUploadBusy) return;
  await ensureProject();
  const f = file || document.getElementById('styleFile').files[0];
  if(!f) return;
  imageUploadBusy = true;
  try{
    const fd = new FormData();
    fd.append('file', namedImageFile(f, 'pasted-style'));
    await api(`/api/projects/${projectId}/style`, {method:'POST', body:fd});
    setStatus('Style загружен и сохранён в каталог');
    refresh();
    setTimeout(()=> nudgeToCard('assignmentCard'), 250);
  }catch(err){
    setStatus('Ошибка загрузки эталона: ' + err.message);
  }finally{
    imageUploadBusy = false;
  }
}
function isTextField(el){
  if(!el) return false;
  if(el.isContentEditable) return true;
  const tag = el.tagName;
  if(tag === 'TEXTAREA') return true;
  if(tag === 'INPUT'){
    const t = (el.type || 'text').toLowerCase();
    return !['button','checkbox','file','radio','range','submit','reset','color','hidden'].includes(t);
  }
  return false;
}
function pasteTargetFromFocus(){
  const active = document.activeElement;
  if(active && (active.id === 'stylePreviewBox' || active.closest('#stylePreviewBox'))) return 'style';
  if(active && (active.id === 'sourcePreviewBox' || active.closest('#sourceCard'))) return 'source';
  return 'source';
}
async function handlePastedImage(event, forcedTarget){
  const file = imageFromClipboard(event);
  if(!file) return false;
  event.preventDefault();
  event.stopPropagation();
  const target = forcedTarget || pasteTargetFromFocus();
  try{
    if(target === 'style') await uploadStyle(file);
    else await uploadSource(file);
  }catch(err){
    setStatus('Ошибка загрузки изображения: ' + err.message);
  }
  return true;
}
async function handleDroppedImage(event, target){
  const file = imageFromDataTransfer(event.dataTransfer);
  if(!file) return;
  event.preventDefault();
  event.currentTarget.classList.remove('paste-hover');
  try{
    if(target === 'style') await uploadStyle(file);
    else await uploadSource(file);
  }catch(err){
    setStatus('Ошибка загрузки изображения: ' + err.message);
  }
}
function setupImagePasteZones(){
  document.addEventListener('paste', async (event) => {
    if(isTextField(document.activeElement)) return;
    if(event.target && event.target.closest && event.target.closest('.paste-zone')) return;
    await handlePastedImage(event);
  });
  for(const [id, target] of [['sourcePreviewBox','source'], ['stylePreviewBox','style']]){
    const box = document.getElementById(id);
    if(!box) continue;
    box.addEventListener('click', () => box.focus());
    box.addEventListener('paste', (event) => { void handlePastedImage(event, target); });
    box.addEventListener('dragover', (event) => { event.preventDefault(); box.classList.add('paste-hover'); });
    box.addEventListener('dragleave', () => box.classList.remove('paste-hover'));
    box.addEventListener('drop', (event) => handleDroppedImage(event, target));
  }
}
async function savePrompt(){
  await ensureProject();
  const fd = new FormData();
  fd.append('prompt', document.getElementById('prompt').value);
  fd.append('facade_mode', document.getElementById('facadeMode').value);
  await api(`/api/projects/${projectId}/prompt`, {method:'POST', body:fd}); setStatus('Задание сохранено'); refreshPipelineLog(false);
}
async function enhancePrompt(){
  await ensureProject();
  await savePrompt();
  const p = await api(`/api/projects/${projectId}/enhance-prompt`, {method:'POST'});
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  setStatus('Задание сжато: короткая и четкая логика для AI');
  refreshPipelineLog(true);
}
function schedulePromptSave(){
  clearTimeout(promptSaveTimer);
  promptSaveTimer = setTimeout(() => { savePrompt().catch(()=>{}); }, 700);
}
async function packageOnly(){
  await ensureProject();
  await savePrompt();
  showGenOverlay('Подготавливаем карту света и промпт...');
  try{
    await api(`/api/projects/${projectId}/package`, {method:'POST'});
    setStatus('Пакет готов — смотрите Артефакты и Журнал pipeline');
    refresh(); refreshPipelineLog(true);
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    hideGenOverlay();
  }
}
async function loadRouterModels(){
  const sel = document.getElementById('routeraiModel');
  try{
    const data = await api('/api/routerai-models');
    routeraiModels = data.models || [];
    if(!sel) return;
    if(!routeraiModels.length){
      sel.innerHTML = '<option value="">Модели недоступны</option>';
      updateRouteraiModelHint();
      return;
    }
    const keep = sel.value;
    sel.innerHTML = routeraiModels.map(m => {
      const eta = m.eta ? ` · ${m.eta}` : '';
      const mark = (m.id === data.default) ? ' ★' : '';
      return `<option value="${esc(m.id)}">${esc(m.label)}${esc(eta)}${mark}</option>`;
    }).join('');
    const rawSaved = localStorage.getItem('niteos_routerai_model') || '';
    // Мягкая миграция на новый default (Gemini 3.1 preview)
    const migrateFrom = !rawSaved || rawSaved === 'google/gemini-2.5-flash-image';
    const saved = normalizeRouteraiModel(
      keep || (migrateFrom ? (data.default || '') : rawSaved) || data.default || ''
    );
    if(!setRouteraiModel(saved) && data.default){
      setRouteraiModel(data.default);
    }
    if(migrateFrom && data.default){
      localStorage.setItem('niteos_routerai_model', data.default);
    }
    updateRouteraiModelHint();
  }catch(err){
    if(sel) sel.innerHTML = '<option value="">Ошибка загрузки моделей</option>';
    updateRouteraiModelHint();
    console.warn('routerai models', err);
  }
}
async function loadDealerTemplates(){
  const scData = await api('/api/client-scenarios');
  dealerScenarios = scData.scenarios || [];
  dealerScenarioCategories = scData.categories || [];
  dealerLegacyRefs = [];
  renderDealerScenarioGrid();
  if(guidedTourMode && helpStepIndex === 1) renderHelpStep();
}
function renderLegacyGroup(){
  return '';
}
function renderDealerScenarioGrid(){
  const grid = document.getElementById('dealerScenarioGrid');
  const items = dealerScenarios.map(s => {
    const thumb = s.has_preview
      ? `<img src="/api/client-scenarios/${s.id}/preview?t=${Date.now()}" alt="">`
      : '<div class="muted" style="font-size:10px;padding:8px">Нет превью</div>';
    return `<div class="scenario-card ${selectedDealerScenarioId===s.id?'selected':''}" onclick="selectDealerScenario('${s.id}')">
      <div class="thumb">${thumb}</div>
      <div class="title">${esc(s.name)}</div>
      <div class="desc">${esc(s.description)}</div>
    </div>`;
  }).join('');
  grid.innerHTML = items
    ? `<div class="category-row"><div class="scroll-hint">Варианты подсветки · 5 в ряд, до 2 строк — дальше прокрутка вниз</div><div class="scenario-catalog-wrap"><div class="scenario-catalog-grid">${items}</div></div></div>`
    : '<div class="muted">Шаблоны не найдены</div>';
}
async function pickLegacyRef(id, libraryPath, name){
  await ensureProject();
  selectedLegacyRefId = id;
  selectedDealerScenarioId = null;
  const fd = new FormData();
  fd.append('library_path', libraryPath);
  fd.append('name', name || id);
  fd.append('template_id', id);
  await api(`/api/projects/${projectId}/dealer-legacy-template`, {method:'POST', body:fd});
  document.getElementById('dealerScenarioStatus').textContent = `Шаблон: ${name || id}`;
  document.getElementById('styleName').textContent = 'Эталон применён';
  renderDealerScenarioGrid();
  setStatus('Шаблон решения применён — эталон и IES подставлены');
  refresh();
  setTimeout(()=> nudgeToCard('assignmentCard'), 250);
}
async function selectDealerScenario(id){
  await ensureProject();
  selectedDealerScenarioId = id;
  selectedLegacyRefId = null;
  const fd = new FormData();
  fd.append('scenario_id', id);
  const p = await api(`/api/projects/${projectId}/dealer-scenario`, {method:'POST', body:fd});
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  document.getElementById('dealerScenarioStatus').textContent = p.dealer_scenario_name
    ? `Выбран: ${p.dealer_scenario_name}${p.dealer_product_name ? ' · ' + p.dealer_product_name : ''}`
    : 'Сценарий применён';
  renderDealerScenarioGrid();
  setStatus('Сценарий применён — эталон, IES и задание обновлены');
  refresh();
  setTimeout(()=> nudgeToCard('assignmentCard'), 250);
}
async function generateVisualization(){
  await ensureProject();
  const btn = document.getElementById('generateBtn');
  if(isGenerating || (btn && btn.disabled)) return;
  if(guidedTourMode){
    guidedGenerateClicked = true;
    const resultIdx = tourStepIndex('result');
    if(resultIdx >= 0 && helpStepIndex < resultIdx){
      helpStepIndex = resultIdx;
      renderHelpStep();
    }
  }
  const fd = new FormData();
  fd.append('prompt', document.getElementById('prompt').value);
  fd.append('facade_mode', document.getElementById('facadeMode').value);
  const modelSel = document.getElementById('routeraiModel');
  if(!modelSel || !modelSel.value){
    setStatus('Выберите модель генерации.');
    return;
  }
  fd.append('routerai_model', modelSel.value);
  localStorage.setItem('niteos_routerai_model', modelSel.value);
  document.getElementById('resultZone').classList.remove('empty');
  const btnLabel = document.getElementById('generateBtnLabel');
  const prevLabel = btnLabel ? btnLabel.textContent : 'Начать генерацию';
  isGenerating = true;
  updateGenerateControls(lastProjectState);
  if(btnLabel) btnLabel.textContent = 'Генерация…';
  const eta = routeraiModelEta(modelSel.value);
  showGenOverlay(
    'Создаём ночную визуализацию по фото и промпту'
    + (eta ? `. Обычно ${eta}` : '. Обычно 20–60 секунд')
    + ` · модель: ${routeraiModelLabel(modelSel.value)}`
  );
  try{
    await api(`/api/projects/${projectId}/render`, {method:'POST', body:fd});
    setStatus('Визуализация готова');
    historyPreviewUrl = '';
    refreshRenderLimit();
    refresh(); refreshPipelineLog(true);
    setTimeout(()=> autoScrollToResult(), 320);
  }catch(err){
    if(err.status === 429){
      setStatus(err.message);
      refreshRenderLimit();
    } else {
      setStatus('Ошибка: ' + err.message);
    }
  }finally{
    isGenerating = false;
    if(btnLabel) btnLabel.textContent = prevLabel;
    updateGenerateControls(lastProjectState);
    updateEditControls(lastProjectState);
    hideGenOverlay();
  }
}
function hasEditableFinal(p){
  const state = p || lastProjectState || {};
  if(state.has_final) return true;
  if(currentFinalUrl) return true;
  const finalImg = document.getElementById('finalImg');
  if(finalImg && finalImg.getAttribute('src')) return true;
  const files = (state.files && state.files.output) || [];
  return files.some(f => f.name === 'final_imported_render.png');
}
async function exportEditAnnotationBlob(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return null;
  const layer = exportEditMarkupLayer();
  if(!layer) return null;
  const maxSide = 1600;
  const sw = canvas.width;
  const sh = canvas.height;
  if(!sw || !sh) return null;
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.round(sw * scale));
  out.height = Math.max(1, Math.round(sh * scale));
  const ctx = out.getContext('2d');
  ctx.clearRect(0, 0, out.width, out.height);
  ctx.drawImage(canvas, 0, 0, out.width, out.height);
  return await new Promise((resolve) => {
    out.toBlob((blob) => resolve(blob || null), 'image/png');
  });
}
async function editRender(){
  await ensureProject();
  const btn = document.getElementById('dealerEditBtn');
  if(!hasEditableFinal()){
    setStatus('Сначала дождитесь результата генерации — затем можно доработать.');
    updateEditControls(lastProjectState);
    return;
  }
  if(isGenerating){
    setStatus('Дождитесь окончания текущей генерации.');
    return;
  }
  const instruction = document.getElementById('editInstruction').value.trim();
  if(!instruction){ setStatus('Напишите, что изменить.'); return; }
  const fd = new FormData();
  fd.append('instruction', instruction);
  const annotationBlob = await exportEditAnnotationBlob();
  if(annotationBlob) fd.append('annotation_file', annotationBlob, 'edit_annotation.png');
  isGenerating = true;
  if(btn){ btn.disabled = true; btn.textContent = 'Доработка…'; }
  showGenOverlay('Отправлена доработка результата...');
  try{
    await api(`/api/projects/${projectId}/edit`, {method:'POST', body:fd});
    clearEditMarkup();
    if(editModeOpen) toggleEditMode(false);
    setStatus('Доработанный результат готов');
    historyPreviewUrl = '';
    refresh(); refreshPipelineLog(true);
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    isGenerating = false;
    hideGenOverlay();
    if(btn) btn.textContent = 'Отправить доработку';
    updateEditControls(lastProjectState);
  }
}
async function previewAgentPlan(){
  return;
}
function renderAgentPreview(_data){
  return;
}
function updateEditControls(p){
  const btn = document.getElementById('dealerEditBtn');
  const toggleBtn = document.getElementById('editModeToggleBtn');
  const hint = document.getElementById('editBtnHint');
  const state = p || lastProjectState || {};
  const canEdit = hasEditableFinal(state) && !isGenerating;
  if(toggleBtn){
    toggleBtn.disabled = !canEdit && !editModeOpen;
    toggleBtn.title = canEdit || editModeOpen
      ? (editModeOpen ? 'Скрыть панель доработки' : 'Открыть доработку поверх результата')
      : (isGenerating ? 'Идёт генерация…' : 'Сначала дождитесь результата генерации');
    toggleBtn.textContent = editModeOpen ? 'Скрыть доработку' : 'Доработать результат';
    toggleBtn.classList.toggle('active', !!editModeOpen);
  }
  if(btn){
    btn.disabled = !canEdit || !editModeOpen;
    btn.title = canEdit
      ? 'Отправить доработку по текущему результату'
      : (isGenerating ? 'Идёт генерация…' : 'Сначала дождитесь результата генерации');
  }
  if(hint){
    hint.textContent = !canEdit
      ? 'Кнопка доработки станет доступной после генерации.'
      : (editModeOpen
        ? 'Рисуйте красным прямо на результате и нажмите «Отправить доработку».'
        : 'Нажмите «Доработать результат», чтобы разметить области на фото.');
  }
}
function toggleEditMode(force){
  if(typeof force === 'boolean') editModeOpen = force;
  else editModeOpen = !editModeOpen;
  if(editModeOpen && !hasEditableFinal()){
    editModeOpen = false;
    setStatus('Сначала дождитесь результата генерации.');
  }
  const section = document.getElementById('editSection');
  const stage = document.getElementById('resultStage');
  const canvas = document.getElementById('editMarkupCanvas');
  if(section) section.classList.toggle('collapsed', !editModeOpen);
  if(stage) stage.classList.toggle('is-editing', editModeOpen);
  if(canvas){
    canvas.classList.toggle('hidden', !editModeOpen);
    canvas.setAttribute('aria-hidden', editModeOpen ? 'false' : 'true');
  }
  editMarkupReady = !!editModeOpen && hasEditableFinal();
  if(editModeOpen){
    syncEditMarkupCanvas();
    const tools = document.getElementById('editToolsPanel');
    if(tools) tools.scrollIntoView({behavior:'smooth', block:'nearest'});
  } else {
    clearEditMarkup();
  }
  updateEditControls(lastProjectState);
}
async function importExisting(){
  const data = await api('/api/library-import-existing', {method:'POST'});
  setStatus('Импорт в каталог: '+JSON.stringify(data.imported)); refreshLibrary();
}
async function addFromLibrary(kind, relativePath){
  await ensureProject();
  const fd = new FormData(); fd.append('relative_path', relativePath);
  await api(`/api/projects/${projectId}/library/${kind}`, {method:'POST', body:fd});
  setStatus('Добавлено в проект из каталога'); refresh();
}
function stepTitle(step){
  const map = {
    render_start: '1. Старт рендера',
    dealer_scenario_applied: 'Сценарий применён',
    dealer_legacy_template_applied: 'Шаблон решения применён',
    dealer_style_ref_applied: 'Референс применён',
    packager_done: '2. Пакетер (опционально)',
    prompt_prepared: '2. Промпт для RouterAI',
    prompt_selected: '3. Промпт для отправки в API',
    routerai_render: '3. Запрос в RouterAI (рендер)',
    enhance_prompt: 'Улучшение задания',
    edit_start: '1. Старт доработки',
    routerai_edit: '2. Запрос в RouterAI (доработка)',
    upload_source: 'Загрузка фото',
    upload_ies: 'Загрузка IES',
    upload_style: 'Загрузка style',
    save_prompt: 'Сохранение задания',
    render_error: 'Ошибка рендера',
    edit_error: 'Ошибка доработки',
    package_done: 'Пакетирование',
    package_error: 'Ошибка пакетирования',
  };
  return map[step] || step;
}
function formatLogEntry(entry){
  const lines = [];
  const payload = {...entry};
  const step = payload.step || 'event';
  delete payload.step;
  delete payload.ts;
  if(payload.user_prompt !== undefined && payload.gemini_prompt !== undefined){
    lines.push('Исходное задание:\\n' + payload.user_prompt);
    if(payload.chatgpt_prompt) lines.push('\\nПромпт для AI (04, русский):\\n' + payload.chatgpt_prompt);
    if(payload.gemini_prompt) lines.push('\\nПромпт Gemini (05):\\n' + payload.gemini_prompt);
    if(payload.ies_summary) lines.push('\\nIES-сводка:\\n' + payload.ies_summary);
    delete payload.user_prompt; delete payload.gemini_prompt; delete payload.chatgpt_prompt; delete payload.ies_summary; delete payload.equipment_draft;
  }
  if(payload.before !== undefined && payload.after !== undefined){
    lines.push('Было:\\n' + payload.before + '\\n\\nСтало:\\n' + payload.after);
    delete payload.before; delete payload.after;
  }
  if(payload.prompt_file){
    lines.push('Файл промпта: ' + payload.prompt_file);
    delete payload.prompt_file;
  }
  if(payload.prompt !== undefined && step.includes('routerai')){
    lines.push('Текст запроса:\\n' + payload.prompt);
    if(payload.images) lines.push('\\nИзображения:\\n' + JSON.stringify(payload.images, null, 2));
    if(payload.model) lines.push('\\nМодель: ' + payload.model);
    if(payload.image_config) lines.push('Параметры image: ' + JSON.stringify(payload.image_config));
    if(payload.response_summary) lines.push('\\nОтвет API:\\n' + JSON.stringify(payload.response_summary, null, 2));
    delete payload.prompt; delete payload.images; delete payload.model; delete payload.image_config; delete payload.response_summary; delete payload.modalities; delete payload.endpoint; delete payload.prompt_chars; delete payload.output; delete payload.http_status;
  }
  const rest = Object.keys(payload).length ? '\\n' + JSON.stringify(payload, null, 2) : '';
  const body = (lines.join('\\n') + rest).trim() || JSON.stringify(entry, null, 2);
  return `<div class="log-entry"><div class="head">${esc(entry.ts || '')} · ${esc(stepTitle(step))}</div><pre>${esc(body)}</pre></div>`;
}
async function refreshPipelineLog(openPanel){
  const logBtn = document.getElementById('downloadLogBtn');
  if(!projectId){
    document.getElementById('pipelineLogPanel').innerHTML = '<div class="muted">Сначала создайте или откройте проект.</div>';
    if(logBtn) logBtn.style.display = 'none';
    return;
  }
  const data = await api(`/api/projects/${projectId}/pipeline-log`);
  const entries = data.entries || [];
  if(logBtn) logBtn.style.display = entries.length ? 'inline-block' : 'none';
  if(!entries.length){
    document.getElementById('pipelineLogPanel').innerHTML = '<div class="muted">Журнал пуст. Запустите рендер или загрузите данные.</div>';
    return;
  }
  document.getElementById('pipelineLogPanel').innerHTML = entries.slice().reverse().map(formatLogEntry).join('');
  if(openPanel) document.getElementById('pipelineLogPanel').classList.add('open');
}
function togglePipelineLog(){
  const panel = document.getElementById('pipelineLogPanel');
  const willOpen = !panel.classList.contains('open');
  panel.classList.toggle('open');
  if(willOpen) refreshPipelineLog(false);
}
function downloadPipelineLog(){
  if(!projectId) return;
  window.open(`/api/projects/${projectId}/pipeline-log/download`, '_blank');
}
function libItem(kind, file){
  const urlPath = file.relative_path.split('/').map(encodeURIComponent).join('/');
  const safePath = file.relative_path.replaceAll("'","\\'");
  let preview;
  if(kind === 'ies' && file.has_photo){
    preview = `<img src="/api/library/ies/photo/${urlPath}?t=${Date.now()}" alt="">`;
  } else if(kind !== 'ies'){
    preview = `<img src="/api/library/${kind}/file/${urlPath}?t=${Date.now()}">`;
  } else {
    preview = `<div class="muted">IES</div>`;
  }
  const extraClass = (kind === 'ies' && file.has_photo) ? ' lib-ies-photo' : '';
  return `<div class="lib-item${extraClass}">${preview}<div class="name" title="${file.relative_path}">${file.name}</div><button onclick="addFromLibrary('${kind}','${safePath}')">В проект</button></div>`;
}
function renderUsedIesCard(item){
  const rel = (item.relative_path || item.name || '').split('/').map(encodeURIComponent).join('/');
  const iesUrl = rel ? `/api/projects/${projectId}/file/ies/${rel}` : '';
  let photo = '';
  if(item.has_photo && rel){
    photo = `<img src="/api/projects/${projectId}/ies-photo/${rel}?t=${Date.now()}" alt="">`;
  } else if(item.product_id){
    photo = `<img src="/api/client-products/${encodeURIComponent(item.product_id)}/preview?t=${Date.now()}" alt="">`;
  } else {
    photo = `<div class="ph">Нет фото</div>`;
  }
  const product = item.product_name || item.product_short || 'Светильник';
  const iesName = item.name || '';
  const dl = iesUrl
    ? `<a class="dl" href="${iesUrl}" target="_blank" rel="noopener">Скачать IES</a>`
    : '';
  return `<div class="render-product-card">${photo}<div class="info"><div class="product">${esc(product)}</div><div class="ies">${esc(iesName)}</div>${dl}</div></div>`;
}
function renderUsedIesCards(p, iesFiles){
  const fromMeta = p.render_ies_items || [];
  const names = p.render_ies_files || [];
  const items = fromMeta.length ? fromMeta : names.map(name => {
    const file = (iesFiles || []).find(f => f.name === name);
    return {
      name,
      relative_path: file?.relative_path || name,
      has_photo: !!file?.has_photo,
      product_name: p.render_product_name || '',
      product_id: p.render_product_id || '',
    };
  });
  return items.map(renderUsedIesCard).join('');
}
function renderIesPreview(iesFiles){
  const row = document.getElementById('iesPreviewRow');
  if(!row) return;
  const withPhoto = (iesFiles || []).filter(f => f.has_photo);
  if(!withPhoto.length){
    row.classList.add('hidden');
    row.innerHTML = '';
    return;
  }
  row.classList.remove('hidden');
  row.innerHTML = withPhoto.map(f => {
    const url = `/api/projects/${projectId}/ies-photo/${f.relative_path.split('/').map(encodeURIComponent).join('/')}?t=${Date.now()}`;
    return `<div class="ies-preview-card" title="${esc(f.name)}">
      <img src="${url}" alt="">
      <div class="cap">${esc(f.name)}</div>
    </div>`;
  }).join('');
}
function historyKindLabel(kind){
  if(kind === 'edit') return 'Доработка';
  if(kind === 'regenerate') return 'Перегенерация';
  return 'Генерация';
}
function renderRenderHistory(history){
  const panel = document.getElementById('renderHistoryPanel');
  const strip = document.getElementById('renderHistoryStrip');
  if(!panel || !strip) return;
  const items = history || [];
  if(!items.length){
    panel.classList.add('hidden');
    strip.innerHTML = '';
    return;
  }
  panel.classList.remove('hidden');
  strip.innerHTML = items.map((h, idx) => {
    const fname = (h.file || '').replace(/^history\//, '');
    const url = `/api/projects/${projectId}/file/history/${encodeURIComponent(fname)}`;
    const active = (!historyPreviewUrl && idx === items.length - 1) || historyPreviewUrl === url ? ' active' : '';
    return `<button type="button" class="render-history-item${active}" onclick="previewHistoryItem('${esc(url)}', ${h.id})">
      <img src="${url}?t=${Date.now()}" alt="">
      <span>${esc(historyKindLabel(h.kind))} #${h.id}</span>
      <span>${esc(routeraiModelShort(h.routerai_model || ''))}</span>
    </button>`;
  }).join('');
}
function previewHistoryItem(url, id){
  historyPreviewUrl = url;
  const img = document.getElementById('finalImg');
  if(img) img.src = url + '?t=' + Date.now();
  setStatus(`Просмотр версии #${id} из истории. Текущий финал не изменён.`);
  if(lastProjectState && lastProjectState.render_history){
    renderRenderHistory(lastProjectState.render_history);
  }
}
function setEditTool(tool){
  editTool = tool === 'eraser' ? 'eraser' : 'brush';
  const brushBtn = document.getElementById('editBrushBtn');
  const eraserBtn = document.getElementById('editEraserBtn');
  if(brushBtn) brushBtn.classList.toggle('active', editTool === 'brush');
  if(eraserBtn) eraserBtn.classList.toggle('active', editTool === 'eraser');
  const canvas = document.getElementById('editMarkupCanvas');
  if(canvas) canvas.style.cursor = editTool === 'eraser' ? 'cell' : 'crosshair';
}
function updateEditBrushSize(v){
  editBrushSize = Math.max(4, Math.min(48, Number(v) || 14));
}
function setupEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  const stage = document.getElementById('resultStage');
  if(!canvas || !stage) return;
  window.addEventListener('resize', () => { if(editModeOpen) syncEditMarkupCanvas(); });
  canvas.addEventListener('pointerdown', (e)=>{ if(!editMarkupReady || !editModeOpen) return; editDrawing=true; editDrawPoint(e, true); canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e)=>{ if(!editMarkupReady || !editModeOpen || !editDrawing) return; editDrawPoint(e, false); });
  canvas.addEventListener('pointerup', ()=>{ editDrawing=false; editLastPoint=null; });
  canvas.addEventListener('pointerleave', ()=>{ editDrawing=false; editLastPoint=null; });
}
function syncEditMarkupCanvas(){
  const canvas = document.getElementById('editMarkupCanvas');
  const stage = document.getElementById('resultStage');
  const img = document.getElementById('finalImg');
  if(!canvas || !stage) return;
  const old = exportEditMarkupLayer();
  const rect = stage.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);
  if(old) restoreEditMarkupLayer(old);
  editMarkupReady = !!editModeOpen && !!(img && img.getAttribute('src'));
}
function editCanvasPoint(e){
  const canvas = document.getElementById('editMarkupCanvas');
  const rect = canvas.getBoundingClientRect();
  return {x:e.clientX-rect.left, y:e.clientY-rect.top};
}
function editDrawPoint(e, start){
  const canvas = document.getElementById('editMarkupCanvas');
  const ctx = canvas.getContext('2d');
  const p = editCanvasPoint(e);
  ctx.lineWidth = editBrushSize;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  if(editTool === 'eraser'){
    ctx.globalCompositeOperation = 'destination-out';
    ctx.strokeStyle = 'rgba(0,0,0,1)';
  } else {
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = '#ff2b2b';
  }
  if(start || !editLastPoint){
    editLastPoint = p;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.01, p.y + 0.01);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(editLastPoint.x, editLastPoint.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    editLastPoint = p;
  }
  ctx.globalCompositeOperation = 'source-over';
}
function loadEditMarkupImage(url){
  // Разметка только по кнопке, прямо на result — без второго окна-копии.
  if(!url){
    if(editModeOpen) toggleEditMode(false);
    editMarkupReady = false;
    clearEditMarkup();
    return;
  }
  if(editModeOpen){
    requestAnimationFrame(() => syncEditMarkupCanvas());
  }
}
function clearEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  editLastPoint = null;
}
function exportEditMarkupLayer(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return '';
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0,0,canvas.width,canvas.height).data;
  for(let i=3;i<data.length;i+=4){ if(data[i] > 0) return canvas.toDataURL('image/png'); }
  return '';
}
function restoreEditMarkupLayer(dataUrl){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !dataUrl) return;
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.drawImage(img, 0, 0, rect.width, rect.height);
  };
  img.src = dataUrl;
}
function exportEditComposite(){
  const baseImg = document.getElementById('finalImg');
  const overlay = document.getElementById('editMarkupCanvas');
  if(!baseImg || !overlay || !baseImg.naturalWidth) return '';
  const markup = exportEditMarkupLayer();
  if(!markup) return '';
  const stage = document.getElementById('resultStage');
  const rect = stage ? stage.getBoundingClientRect() : {width: baseImg.clientWidth, height: baseImg.clientHeight};
  const w = Math.max(1, Math.round(rect.width));
  const h = Math.max(1, Math.round(rect.height));
  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  const ctx = out.getContext('2d');
  ctx.drawImage(baseImg, 0, 0, w, h);
  ctx.drawImage(overlay, 0, 0, w, h);
  return out.toDataURL('image/png');
}
function downloadFinal(){
  if(currentFinalUrl) window.open(currentFinalUrl, '_blank');
}

function regenerate(){
  if(!projectId) return;
  generateVisualization();
}
function downloadProjectZip(){
  if(!projectId) return;
  window.open(`/api/projects/${projectId}/download.zip`, '_blank');
}
function renderArtifacts(files){
  const latest = files.latest || [];
  const items = [
    ['04_prompt_for_chatgpt.txt', 'Промпт для AI (русский)'],
    ['05_prompt_for_gemini_nano_banana.txt', 'Промпт Gemini'],
    ['07_ies_summary.txt', 'IES-сводка'],
    ['08_equipment_draft.md', 'Ведомость'],
    ['04_prompt_for_chatgpt.txt', 'Промпт ChatGPT'],
    ['02_light_plan_reference.png', 'Карта света'],
    ['01_source_building.png', 'Исходник'],
  ];
  const links = items
    .filter(([name]) => latest.some(f => f.name === name))
    .map(([name, label]) => {
      const file = latest.find(f => f.name === name);
      const url = `/api/projects/${projectId}/file/latest/${file.relative_path}`;
      return `<a href="${url}" target="_blank" rel="noopener">${label}</a>`;
    });
  document.getElementById('artifactsHint').style.display = links.length ? 'none' : 'block';
  document.getElementById('artifactsLinks').innerHTML = links.join('');
  document.getElementById('downloadZipBtn').style.display = projectId ? 'inline-block' : 'none';
}
async function refreshLibrary(){
  const data = await api('/api/library');
  document.getElementById('sourceLibrary').innerHTML = (data.source||[]).map(f=>libItem('source',f)).join('') || '<div class="muted">Нет сохраненных фото</div>';
  document.getElementById('iesLibrary').innerHTML = (data.ies||[]).map(f=>libItem('ies',f)).join('') || '<div class="muted">Каталог IES пуст</div>';
}

async function adminAddLibraryIes(){
  const pass = document.getElementById('catalogPass').value || '';
  const ies = document.getElementById('catalogIesFile').files[0];
  const photo = document.getElementById('catalogIesPhoto').files[0];
  if(!ies){
    setStatus('Выберите IES-файл');
    return;
  }
  const fd = new FormData();
  fd.append('password', pass);
  fd.append('ies', ies);
  if(photo) fd.append('photo', photo);
  try{
    await api('/api/admin/library/ies', {method:'POST', body:fd});
    setStatus('IES добавлен в каталог' + (photo ? ' (с фото)' : ''));
    document.getElementById('catalogIesFile').value = '';
    document.getElementById('catalogIesPhoto').value = '';
    refreshLibrary();
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }
}

async function adminDeleteLibraryIes(){
  const pass = document.getElementById('catalogPass').value || '';
  const path = (document.getElementById('catalogIesDeletePath').value || '').trim();
  if(!path){
    setStatus('Укажите имя IES-файла для удаления');
    return;
  }
  const fd = new FormData();
  fd.append('password', pass);
  fd.append('relative_path', path);
  try{
    await api('/api/admin/library/ies', {method:'DELETE', body:fd});
    setStatus('Удалено из каталога');
    document.getElementById('catalogIesDeletePath').value = '';
    refreshLibrary();
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }
}
async function refresh(){
  if(!projectId) return;
  const p = await api(`/api/projects/${projectId}`);
  lastProjectState = p;
  const files = p.files || {};
  const source = (files.input || []).find(f=>f.name==='building.png');
  const style = (files.references || []).find(f=>f.name==='style_reference_target.png');
  const ies = files.ies || [];
  const light = (files.latest || []).find(f=>f.name==='02_light_plan_reference.png');
  const final = (files.output || []).find(f=>f.name==='final_imported_render.png');
  const sourceBox = document.getElementById('sourcePreviewBox');
  if(source){
    sourceBox.innerHTML = `<img src="/api/projects/${projectId}/file/input/${source.relative_path}?t=${Date.now()}">`;
    sourceBox.classList.add('has-image');
  } else {
    sourceBox.innerHTML = 'Фото здания днём · Ctrl+V или перетащите';
    sourceBox.classList.remove('has-image');
  }
  document.getElementById('sourceName').textContent = source ? `Фото: ${source.name}` : 'Файл не выбран';
  const styleBox = document.getElementById('stylePreviewBox');
  if(style){
    styleBox.innerHTML = `<img src="/api/projects/${projectId}/file/references/${style.relative_path}?t=${Date.now()}">`;
    styleBox.classList.add('has-image');
  } else {
    styleBox.innerHTML = 'Текущий эталон · Ctrl+V для своего';
    styleBox.classList.remove('has-image');
  }
  document.getElementById('styleName').textContent = style ? `Эталон: ${style.name}` : 'Эталон не выбран';
  document.getElementById('iesStatusBox').innerHTML = ies.length ? `Загружено IES: ${ies.length}` : 'IES: нет · подставятся при выборе сценария';
  document.getElementById('iesName').textContent = ies.length ? ies.map(f=>f.name).join(', ') : 'Файлы не выбраны';
  // IES preview / «Светильник и IES» в результате клиенту не показываем
  const renderUsedBlock = document.getElementById('renderUsedBlock');
  if(renderUsedBlock){
    renderUsedBlock.classList.add('hidden');
    renderUsedBlock.style.display = 'none';
  }
  const regenBtn = document.getElementById('regenerateBtn');
  if(regenBtn) regenBtn.style.display = final ? 'inline-block' : 'none';
  const auditBox = document.getElementById('renderAudit');
  const audit = p.render_audit || {};
  if(auditBox){
    const shouldShowAudit = !!final && audit.status && audit.status !== 'ok';
    if(shouldShowAudit){
      const gaps = (audit.dark_zones || []).join(', ');
      const prefix = audit.status === 'low_signal'
        ? 'AI-проверка: кадр слишком тёмный для надёжной оценки покрытия.'
        : 'AI-проверка: возможны зоны без нужного света.';
      auditBox.textContent = `${prefix} Покрытие: ${audit.coverage_score || 0}%.${gaps ? ' Зоны: ' + gaps + '.' : ''}`;
      auditBox.classList.remove('hidden');
    } else {
      auditBox.textContent = '';
      auditBox.classList.add('hidden');
    }
  }
  updateWorkflowFromProject(p);
  checkGuidedTourAdvance(p);
  if(p.dealer_scenario_id) selectedDealerScenarioId = p.dealer_scenario_id;
  if(p.dealer_scenario_name){
    document.getElementById('dealerScenarioStatus').textContent =
      `Выбран: ${p.dealer_scenario_name}${p.dealer_product_name ? ' · ' + p.dealer_product_name : ''}`;
  }
  const lightImg = document.getElementById('lightImg');
  if(lightImg) lightImg.src = light ? `/api/projects/${projectId}/file/latest/${light.relative_path}?t=${Date.now()}` : '';
  currentFinalUrl = final ? `/api/projects/${projectId}/file/output/${final.relative_path}?t=${Date.now()}` : '';
  if(!historyPreviewUrl){
    document.getElementById('finalImg').src = currentFinalUrl;
  }
  renderRenderHistory(p.render_history || []);
  loadEditMarkupImage(final ? currentFinalUrl : '');
  updateEditControls(p);
  document.getElementById('statusText').textContent = final ? 'Финальный рендер готов' : 'Результат появится здесь после генерации';
  if(final) document.getElementById('resultZone').classList.remove('empty');
  hideContactCta();
  renderArtifacts(files);
  refreshPipelineLog(false);
  refreshLibrary();
  if(p.prompt !== undefined) document.getElementById('prompt').value = p.prompt || '';
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  if(p.routerai_model) setRouteraiModel(p.routerai_model);
  updateGenerateControls(p);
  updateEditControls(p);
  scheduleFeedbackPrompt(p);
}
setupEditMarkup();
setEditTool('brush');
setupImagePasteZones();
setDealerWorkMode(dealerWorkMode);
loadDealerTemplates();
loadRouterModels().then(() => {
  if(lastProjectState && lastProjectState.routerai_model){
    setRouteraiModel(lastProjectState.routerai_model);
  }
  updateGenerateControls(lastProjectState);
});
refreshLibrary();
refreshRenderLimit();
const dealerProject = new URLSearchParams(location.search).get('project');
if(dealerProject) openProject(dealerProject);
else initWelcomeFromLanding();
</script>
</body>
</html>
"""

CLIENT_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS — для клиентов</title>
  <style>
    body{margin:0;background:#05070a;color:#eef2f6;font-family:Segoe UI,Arial,sans-serif}
    main.client-page{max-width:1100px;margin:0 auto;padding:20px 20px 48px}
    section.panel{border:1px solid #2b333d;background:#0b0f14;border-radius:14px;padding:18px;margin-bottom:16px}
    h1{font-size:26px;margin:0} h2{font-size:15px;color:#cbd5e1;margin:0 0 10px;font-weight:700}
    h3{font-size:13px;color:#8d97a3;margin:0 0 8px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
    textarea,button{box-sizing:border-box;border-radius:10px;border:1px solid #34404c;background:#070a0e;color:#eef2f6;padding:10px;font:inherit}
    textarea{width:100%;min-height:90px;resize:vertical}
    button{background:#d8e0ea;color:#05070a;font-weight:700;cursor:pointer}
    button.secondary{background:#151b22;color:#eef2f6}
    button:disabled{opacity:.45;cursor:not-allowed}
    .muted{color:#8d97a3;font-size:13px;line-height:1.45}
    .hidden{display:none!important}
    .step-block{margin-bottom:20px}
    .step-block:last-child{margin-bottom:0}
    .step-head{display:flex;align-items:center;gap:10px;margin-bottom:8px}
    .step-head .badge{width:30px;height:30px;border-radius:10px;background:#d8e0ea;color:#05070a;display:inline-grid;place-items:center;font-weight:700;flex-shrink:0}
    .step-head .label{font-size:17px;font-weight:700}
    .preview-box{height:140px;border:1px solid #27313b;border-radius:12px;background:#05070a;display:grid;place-items:center;color:#8d97a3;overflow:hidden;outline:none}
    .preview-box:focus,.preview-box.paste-hover{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.35)}
    .preview-box img{width:100%;height:100%;object-fit:contain;border:0;border-radius:0}
    .source-preview-box{min-height:160px;border:1px solid #27313b;border-radius:12px;background:#05070a;display:flex;align-items:center;justify-content:center;color:#8d97a3;overflow:auto;outline:none;padding:10px;text-align:center;font-size:13px;line-height:1.4}
    .source-preview-box.has-image{align-items:flex-start;justify-content:center;padding:6px;max-height:min(72vh,560px)}
    .source-preview-box:focus,.source-preview-box.paste-hover{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.35)}
    .source-preview-box img{display:block;max-width:100%;width:auto;height:auto;max-height:min(70vh,540px);object-fit:contain;border:0;border-radius:6px;margin:0 auto}
    .status-line{color:#8d97a3;font-size:13px;margin:8px 0 0;min-height:18px}
    .page-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}
    .help-btn{width:auto;margin:0;padding:8px 12px;font-size:12px}
    .back-link{display:inline-block;margin-bottom:10px;color:#9ec5ff;text-decoration:none;font-size:13px}
    .back-link:hover{text-decoration:underline}
    .h-scroll{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 10px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}
    .h-scroll::-webkit-scrollbar{height:7px}
    .h-scroll::-webkit-scrollbar-thumb{background:#34404c;border-radius:4px}
    .h-scroll::-webkit-scrollbar-track{background:#0a0e13}
    .scroll-hint{font-size:12px;color:#6b7580;margin:0 0 8px}
    .product-showcase .product-card{flex:0 0 270px;scroll-snap-align:start;border:1px solid #27313b;border-radius:12px;padding:10px;background:#070a0e;cursor:default}
    .product-card .thumb{height:148px;border-radius:8px;border:1px solid #27313b;background:#030405;display:grid;place-items:center;overflow:hidden;margin-bottom:8px}
    .product-card .thumb img{width:100%;height:100%;object-fit:cover}
    .product-card .title{font-weight:700;font-size:13px;color:#e8eef6;margin-bottom:3px}
    .product-card .desc{font-size:11px;color:#8d97a3;line-height:1.35}
    .scenario-card{flex:0 0 230px;scroll-snap-align:start;border:2px solid #27313b;border-radius:12px;padding:9px;background:#070a0e;cursor:pointer;transition:border-color .15s,box-shadow .15s}
    .scenario-card:hover,.scenario-card.selected{border-color:#5a7a9a;box-shadow:0 0 0 2px rgba(90,122,154,.22)}
    .scenario-card .thumb{height:158px;border-radius:8px;border:1px solid #27313b;background:#030405;overflow:hidden;margin-bottom:7px}
    .scenario-card .thumb.thumb-prompt-stale{border:2px solid #e04545;box-shadow:0 0 0 1px rgba(224,69,69,.35)}
    .scenario-card .thumb img{width:100%;height:100%;object-fit:cover}
    .scenario-card .title{font-weight:700;font-size:12px;color:#e8eef6;margin-bottom:2px;line-height:1.25}
    .scenario-card .desc{font-size:10px;color:#8d97a3;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
    .category-row{margin-bottom:14px}
    .category-row:last-child{margin-bottom:0}
    .generate-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:16px;padding-top:16px;border-top:1px solid #27313b}
    .generate-row button{width:auto;min-width:200px;margin:0}
    .selection-summary{font-size:13px;color:#9aa6b2;flex:1;min-width:180px}
    details{border:1px solid #27313b;border-radius:12px;padding:10px;margin:12px 0 0;background:#070a0e}
    summary{cursor:pointer;color:#cbd5e1;font-weight:700}
    .result-zone{border:1px solid #2b333d;background:#090d12;border-radius:14px;padding:18px;margin-top:8px}
    .result-zone.empty{display:none}
    .compare-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:12px 0}
    @media(max-width:720px){.compare-row{grid-template-columns:1fr}}
    .compare-card{border:1px solid #27313b;border-radius:12px;background:#05070a;overflow:hidden}
    .compare-card .cap{padding:8px 12px;font-size:12px;font-weight:700;color:#9aa6b2;border-bottom:1px solid #27313b;background:#0b0f14}
    .compare-card .imgbox{min-height:180px;display:flex;align-items:center;justify-content:center;background:#030405;padding:6px;overflow:auto;max-height:min(72vh,560px)}
    .compare-card .imgbox img{max-width:100%;width:auto;height:auto;max-height:min(68vh,520px);object-fit:contain;display:block;border:0;border-radius:0;margin:0 auto}
    .compare-card .imgbox .placeholder{color:#6b7580;font-size:13px;padding:20px;text-align:center}
    .result-actions{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}
    .result-actions button{width:auto;margin:0}
    .result-stage{position:relative;border:1px solid #27313b;border-radius:12px;background:#030405;overflow:hidden}
    .gen-overlay{position:absolute;inset:0;display:none;place-items:center;background:rgba(3,4,5,.82);z-index:5;text-align:center;padding:20px}
    .gen-overlay.open{display:grid}
    .gen-overlay .box{border:1px solid #3a4d63;border-radius:14px;background:#0b1017;padding:18px 22px;max-width:320px}
    .gen-overlay .title{font-weight:700;color:#e8eef6;margin-bottom:8px}
    .gen-overlay .text{font-size:13px;color:#9aa6b2;line-height:1.45}
    .spinner{width:34px;height:34px;border:3px solid #2b333d;border-top-color:#9ec5ff;border-radius:50%;margin:0 auto 12px;animation:spin 1s linear infinite}
    @keyframes spin{to{transform:rotate(360deg)}}
    .help-modal{position:fixed;inset:0;display:none;place-items:center;background:rgba(0,0,0,.65);z-index:50;padding:20px}
    .help-modal.open{display:grid}
    .help-modal .panel{max-width:560px;width:100%;border:1px solid #2b333d;border-radius:14px;background:#0b0f14;padding:18px}
    .help-modal ul{margin:0;padding-left:18px;color:#cbd5e1;line-height:1.55}
    .help-modal .actions{margin-top:14px}
    .help-modal .actions button{width:auto;margin:0}
    .edit-block{margin-top:16px;padding-top:16px;border-top:1px solid #27313b}
    .edit-block button{width:100%;margin-top:10px}
  </style>
</head>
<body>
<div class="help-modal" id="helpModal" onclick="if(event.target===this) closeHelp()">
  <div class="panel">
    <h3 id="helpTitle">Как это работает</h3>
    <div id="helpBody"></div>
    <div class="actions"><button class="secondary" onclick="closeHelp()">Понятно</button></div>
  </div>
</div>
<main class="client-page">
  <a class="back-link" href="/">← На главную</a>
  <div class="page-head">
    <div>
      <h1>Для клиентов</h1>
      <div class="muted" id="projectInfo">Новая визуализация</div>
    </div>
    <button class="secondary help-btn" onclick="openHelp()">Как это работает</button>
  </div>

  <section class="panel" id="setupPanel">
    <h2>Настройка визуализации</h2>
    <div class="muted" style="margin-bottom:16px">Сверху вниз: фото → представленная продукция → выбор сценария.</div>

    <div class="step-block">
      <div class="step-head"><span class="badge">1</span><span class="label">Фото фасада (день)</span></div>
      <div class="source-preview-box paste-zone" id="clientSourcePreview" tabindex="0">Фото здания днём · Ctrl+V или перетащите</div>
      <div class="status-line" id="clientSourceName">Файл не выбран</div>
      <input class="hidden" id="clientSourceFile" type="file" accept="image/*" onchange="uploadClientSource()">
      <button class="secondary" style="margin-top:10px;width:auto" onclick="chooseFile('clientSourceFile')">Выбрать фото</button>
    </div>

    <div class="step-block">
      <div class="step-head"><span class="badge">2</span><span class="label">Представленная продукция</span></div>
      <div class="muted" style="margin-bottom:8px">Имеющаяся продукция NITEOS — для ознакомления. Выбор сценария ниже.</div>
      <div class="scroll-hint">← прокрутите горизонтально →</div>
      <div class="h-scroll product-showcase" id="productGrid"></div>
    </div>

    <div class="step-block">
      <div class="step-head"><span class="badge">3</span><span class="label">Сценарии применения</span></div>
      <div class="muted" id="scenarioStepHint" style="margin-bottom:8px">Выберите схему подсветки — AI перенесёт её на ваше здание.</div>
      <div id="scenarioGrid"></div>
      <details>
        <summary>Изменить задание (необязательно)</summary>
        <textarea id="clientPrompt" placeholder="Оставьте пустым — будет использован текст сценария"></textarea>
      </details>
      <div class="generate-row">
        <div class="selection-summary" id="selectionSummary">Загрузите фото и выберите сценарий</div>
        <button id="clientRenderBtn" onclick="clientRender()" disabled>Создать визуализацию</button>
        <button class="secondary" onclick="clientRender()">Пересоздать</button>
      </div>
    </div>
    <div class="status-line" id="statusText" style="margin-top:4px">Загрузите фото и выберите сценарий</div>
  </section>

  <section class="result-zone empty" id="resultZone">
    <h2>Результат</h2>
    <div class="muted" id="resultStatusText">Сравнение «до» и «после» появится здесь после генерации</div>
    <div class="compare-row">
      <div class="compare-card">
        <div class="cap">До — исходное фото</div>
        <div class="imgbox" id="beforeBox"><div class="placeholder">Загрузите фото на шаге 1</div></div>
      </div>
      <div class="compare-card">
        <div class="cap">После — ночная визуализация</div>
        <div class="result-stage imgbox" id="resultStage">
          <div class="gen-overlay" id="genOverlay">
            <div class="box">
              <div class="spinner"></div>
              <div class="title">Идёт генерация</div>
              <div class="text" id="genOverlayText">Создаём ночную визуализацию. Обычно 20–60 секунд.</div>
            </div>
          </div>
          <div class="placeholder" id="afterPlaceholder">Результат появится после нажатия «Создать визуализацию»</div>
          <img id="finalImg" class="hidden" alt="">
        </div>
      </div>
    </div>
    <div class="result-actions">
      <button class="secondary" onclick="downloadFinal()">Скачать результат</button>
    </div>
    <div class="edit-block">
      <h2>Уточнить результат</h2>
      <textarea id="clientEditInstruction" placeholder="Например: добавь подсветку на левое крыло"></textarea>
      <button onclick="clientEditRender()">Применить изменение</button>
    </div>
  </section>
</main>
<script>
let projectId = null;
let clientProducts = [];
let clientScenarios = [];
let scenarioCategories = [];
const SCENARIO_PRODUCT = {linear:'magistral', projector:'xray', ground:'ntpark'};
let selectedScenarioId = null;
let clientProjectReady = false;
let currentFinalUrl = '';
let currentSourceUrl = '';
const setStatus = (t) => { document.getElementById('statusText').textContent = t; };
const HELP_TEXT = `<ul>
  <li><b>Шаг 1</b> — загрузите дневное фото здания.</li>
  <li><b>Шаг 2</b> — ознакомьтесь с представленной продукцией NITEOS.</li>
  <li><b>Шаг 3</b> — выберите сценарий подсветки (прокрутите ряды горизонтально).</li>
  <li>Нажмите «Создать визуализацию» — ниже откроется сравнение «до / после».</li>
</ul>`;
function openHelp(){
  document.getElementById('helpTitle').textContent = 'Как это работает — для клиентов';
  document.getElementById('helpBody').innerHTML = HELP_TEXT;
  document.getElementById('helpModal').classList.add('open');
}
function closeHelp(){ document.getElementById('helpModal').classList.remove('open'); }
function showGenOverlay(text){
  document.getElementById('genOverlayText').textContent = text || 'Идёт генерация...';
  document.getElementById('genOverlay').classList.add('open');
  document.getElementById('resultZone').classList.remove('empty');
  document.getElementById('resultZone').scrollIntoView({behavior:'smooth', block:'start'});
}
function hideGenOverlay(){ document.getElementById('genOverlay').classList.remove('open'); }
function updateSelectionSummary(){
  const s = clientScenarios.find(x => x.id === selectedScenarioId);
  const parts = [];
  if(clientProjectReady) parts.push('Фото ✓');
  if(s) parts.push(s.name);
  document.getElementById('selectionSummary').textContent = parts.length
    ? parts.join(' · ')
    : 'Загрузите фото и выберите сценарий';
}
function productIdForScenario(scenarioId){
  const sc = clientScenarios.find(s => s.id === scenarioId);
  return sc ? (SCENARIO_PRODUCT[sc.category] || 'magistral') : 'magistral';
}
function showResultZone(hasFinal){
  const zone = document.getElementById('resultZone');
  if(hasFinal || document.getElementById('genOverlay').classList.contains('open')){
    zone.classList.remove('empty');
  }
}
function updateBeforeAfter(){
  const beforeBox = document.getElementById('beforeBox');
  if(currentSourceUrl){
    beforeBox.innerHTML = `<img src="${currentSourceUrl}" alt="До">`;
  } else {
    beforeBox.innerHTML = '<div class="placeholder">Загрузите фото на шаге 1</div>';
  }
  const finalImg = document.getElementById('finalImg');
  const afterPh = document.getElementById('afterPlaceholder');
  if(currentFinalUrl){
    finalImg.src = currentFinalUrl;
    finalImg.classList.remove('hidden');
    afterPh.classList.add('hidden');
    showResultZone(true);
    document.getElementById('resultStatusText').textContent = 'Сравните исходное фото и ночную визуализацию';
  } else {
    finalImg.classList.add('hidden');
    finalImg.removeAttribute('src');
    afterPh.classList.remove('hidden');
  }
}
async function api(path, opts={}) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
function esc(value){
  return String(value || '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
}
function chooseFile(inputId){
  const input = document.getElementById(inputId);
  input.value = '';
  input.click();
}
function namedImageFile(file, prefix){
  if(file.name) return file;
  const ext = (file.type || 'image/png').split('/')[1] || 'png';
  return new File([file], `${prefix}-${Date.now()}.${ext}`, {type: file.type || 'image/png'});
}
function imageFromClipboard(event){
  const items = event.clipboardData && event.clipboardData.items;
  if(!items) return null;
  for(const item of items){
    if(item.kind === 'file' && item.type && item.type.startsWith('image/')) return item.getAsFile();
  }
  return null;
}
function imageFromDataTransfer(dt){
  if(!dt) return null;
  if(dt.files && dt.files.length){
    for(const f of dt.files){ if(f.type && f.type.startsWith('image/')) return f; }
  }
  return null;
}
async function ensureClientProject(){
  if(!projectId){
    const fd = new FormData();
    fd.append('name', 'Client project');
    fd.append('mode', 'client');
    const p = await api('/api/projects', {method:'POST', body:fd});
    projectId = p.id;
    document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  }
}
async function loadClientCatalog(){
  const [productsData, scenariosData] = await Promise.all([
    api('/api/client-products'),
    api('/api/client-scenarios'),
  ]);
  clientProducts = productsData.products || [];
  clientScenarios = scenariosData.scenarios || [];
  scenarioCategories = scenariosData.categories || [];
  renderProductGrid();
  renderScenarioGrid();
  updateSelectionSummary();
}
function renderProductGrid(){
  document.getElementById('productGrid').innerHTML = clientProducts.map(p => {
    const thumb = p.has_preview
      ? `<img src="/api/client-products/${p.id}/preview?t=${Date.now()}" alt="">`
      : '<span class="muted" style="font-size:11px">Нет превью</span>';
    return `<div class="product-card">
      <div class="thumb">${thumb}</div>
      <div class="title">${esc(p.short_name || p.name)}</div>
      <div class="desc">${esc(p.description)}</div>
    </div>`;
  }).join('') || '<div class="muted">Продукция не найдена</div>';
}
function renderScenarioGrid(){
  const grid = document.getElementById('scenarioGrid');
  const items = clientScenarios.map(s => {
    const thumb = s.has_preview
      ? `<img src="/api/client-scenarios/${s.id}/preview?t=${Date.now()}" alt="">`
      : '<div class="placeholder" style="font-size:10px;padding:8px">Пример</div>';
    return `<div class="scenario-card ${selectedScenarioId===s.id?'selected':''}" onclick="selectScenario('${s.id}')">
      <div class="thumb">${thumb}</div>
      <div class="title">${esc(s.name)}</div>
      <div class="desc">${esc(s.description)}</div>
    </div>`;
  }).join('');
  grid.innerHTML = items
    ? `<div class="category-row">
      <h3>Варианты подсветки</h3>
      <div class="scroll-hint">← прокрутите →</div>
      <div class="h-scroll">${items}</div>
    </div>`
    : '<div class="muted">Сценарии не найдены</div>';
}
function selectScenario(id){
  selectedScenarioId = id;
  const sc = clientScenarios.find(s => s.id === id);
  if(sc && !document.getElementById('clientPrompt').value.trim()) {
    document.getElementById('clientPrompt').placeholder = sc.prompt_preview || 'Текст сценария';
  }
  renderScenarioGrid();
  updateClientRenderButton();
  updateSelectionSummary();
}
function updateClientRenderButton(){
  document.getElementById('clientRenderBtn').disabled = !(clientProjectReady && selectedScenarioId);
}
async function uploadClientSource(file){
  await ensureClientProject();
  const f = file || document.getElementById('clientSourceFile').files[0];
  if(!f) return;
  const fd = new FormData();
  fd.append('file', namedImageFile(f, 'client-source'));
  await api(`/api/projects/${projectId}/source`, {method:'POST', body:fd});
  clientProjectReady = true;
  setStatus('Фото загружено. Выберите сценарий.');
  updateClientRenderButton();
  refreshClientPreview();
}
function refreshClientPreview(){
  if(!projectId) return;
  api(`/api/projects/${projectId}`).then(p => {
    const source = (p.files?.input || []).find(f => f.name === 'building.png');
    const box = document.getElementById('clientSourcePreview');
    currentSourceUrl = source ? `/api/projects/${projectId}/file/input/${source.relative_path}?t=${Date.now()}` : '';
    box.classList.toggle('has-image', !!source);
    box.innerHTML = source
      ? `<img src="${currentSourceUrl}" alt="Фото фасада">`
      : 'Фото здания днём · Ctrl+V или перетащите';
    document.getElementById('clientSourceName').textContent = source ? `Фото: ${source.name}` : 'Файл не выбран';
    clientProjectReady = !!source;
    updateClientRenderButton();
    if(p.client_scenario_id) selectedScenarioId = p.client_scenario_id;
    const final = (p.files?.output || []).find(f => f.name === 'final_imported_render.png');
    currentFinalUrl = final ? `/api/projects/${projectId}/file/output/${final.relative_path}?t=${Date.now()}` : '';
    updateBeforeAfter();
    setStatus(final ? 'Визуализация готова — результат ниже' : 'Загрузите фото и выберите сценарий');
    updateSelectionSummary();
    loadClientCatalog();
  }).catch(()=>{});
}
async function clientRender(){
  if(!selectedScenarioId){ setStatus('Сначала выберите сценарий.'); return; }
  await ensureClientProject();
  if(!clientProjectReady){ setStatus('Сначала загрузите фото фасада.'); return; }
  const fd = new FormData();
  fd.append('scenario_id', selectedScenarioId);
  fd.append('product_id', productIdForScenario(selectedScenarioId));
  fd.append('prompt_override', document.getElementById('clientPrompt').value.trim());
  showGenOverlay('Создаём ночную визуализацию по выбранному сценарию...');
  try{
    await api(`/api/projects/${projectId}/client-render`, {method:'POST', body:fd});
    setStatus('Визуализация готова — результат ниже');
    refreshClientPreview();
    document.getElementById('resultZone').scrollIntoView({behavior:'smooth', block:'start'});
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    hideGenOverlay();
  }
}
async function clientEditRender(){
  if(!projectId) return;
  const instruction = document.getElementById('clientEditInstruction').value.trim();
  if(!instruction){ setStatus('Напишите, что изменить.'); return; }
  const fd = new FormData();
  fd.append('instruction', instruction);
  showGenOverlay('Уточняем результат...');
  try{
    await api(`/api/projects/${projectId}/edit`, {method:'POST', body:fd});
    setStatus('Результат обновлён');
    refreshClientPreview();
    document.getElementById('resultZone').scrollIntoView({behavior:'smooth', block:'start'});
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    hideGenOverlay();
  }
}
function downloadFinal(){
  if(currentFinalUrl) window.open(currentFinalUrl, '_blank');
}
function setupClientPaste(){
  const box = document.getElementById('clientSourcePreview');
  box.addEventListener('click', () => box.focus());
  box.addEventListener('paste', async (event) => {
    const file = imageFromClipboard(event);
    if(!file) return;
    event.preventDefault();
    await uploadClientSource(file);
  });
  box.addEventListener('dragover', (e) => { e.preventDefault(); box.classList.add('paste-hover'); });
  box.addEventListener('dragleave', () => box.classList.remove('paste-hover'));
  box.addEventListener('drop', async (e) => {
    const file = imageFromDataTransfer(e.dataTransfer);
    if(!file) return;
    e.preventDefault();
    box.classList.remove('paste-hover');
    await uploadClientSource(file);
  });
}
loadClientCatalog();
setupClientPaste();
const clientProject = new URLSearchParams(location.search).get('project');
if(clientProject){
  projectId = clientProject;
  document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  refreshClientPreview();
}
</script>
</body>
</html>
"""
