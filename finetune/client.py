# -*- coding: utf-8 -*-
"""HTTP client for fine-tuned Flux LoRA inference endpoint."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

from finetune import FINETUNED_MODEL_ID, TRIGGER_TOKEN


def finetuned_endpoint_configured() -> bool:
    return bool(os.getenv("FINETUNED_IMAGE_API_URL", "").strip())


def finetuned_api_url() -> str:
    return os.getenv("FINETUNED_IMAGE_API_URL", "").strip().rstrip("/")


def finetuned_api_key() -> str:
    return os.getenv("FINETUNED_IMAGE_API_KEY", "").strip()


def finetuned_lora_id() -> str:
    return os.getenv("FINETUNED_LORA_ID", "niteos_archlight_v1").strip() or "niteos_archlight_v1"


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _ensure_trigger(prompt: str) -> str:
    text = (prompt or "").strip()
    if TRIGGER_TOKEN not in text:
        text = f"{TRIGGER_TOKEN}. {text}"
    return text


def generate_finetuned_image(
    prompt: str,
    image_paths: list[Path],
    out_path: Path,
    *,
    aspect_ratio: str = "16:9",
) -> tuple[Path, dict]:
    """
    Contract: POST {url}/v1/images/generate
    JSON: {prompt, lora_id, aspect_ratio, images:[{name, data_url}]}
    Response: {image: data_url} or {image_base64: "..."} or OpenAI-like data[0].b64_json
    """
    base_url = finetuned_api_url()
    if not base_url:
        raise RuntimeError("FINETUNED_IMAGE_API_URL is not set")

    images_payload = []
    for path in image_paths:
        if path.exists():
            images_payload.append({"name": path.name, "data_url": _data_url(path)})

    body = {
        "model": FINETUNED_MODEL_ID,
        "lora_id": finetuned_lora_id(),
        "prompt": _ensure_trigger(prompt),
        "aspect_ratio": aspect_ratio,
        "images": images_payload,
    }
    headers = {"Content-Type": "application/json"}
    key = finetuned_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    url = f"{base_url}/v1/images/generate"
    api_log = {
        "model": FINETUNED_MODEL_ID,
        "endpoint": url,
        "lora_id": body["lora_id"],
        "prompt": body["prompt"],
        "prompt_chars": len(body["prompt"]),
        "images": [{"name": i["name"]} for i in images_payload],
        "image_config": {"aspect_ratio": aspect_ratio},
        "backend": "finetuned_lora",
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Fine-tuned API HTTP {exc.code}: {detail[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Fine-tuned API failed: {exc}") from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image_value = data.get("image") or data.get("image_url") or ""
    if not image_value and isinstance(data.get("data"), list) and data["data"]:
        first = data["data"][0] or {}
        if first.get("b64_json"):
            image_value = f"data:image/png;base64,{first['b64_json']}"
        else:
            image_value = first.get("url") or ""
    if not image_value and data.get("image_base64"):
        image_value = f"data:image/png;base64,{data['image_base64']}"

    if not image_value:
        raise RuntimeError("Fine-tuned API response has no image")

    if image_value.startswith("data:"):
        raw_bytes = base64.b64decode(image_value.split(",", 1)[1])
        out_path.write_bytes(raw_bytes)
    else:
        with urllib.request.urlopen(image_value, timeout=240) as response:
            out_path.write_bytes(response.read())

    api_log["ok"] = True
    api_log["out_path"] = str(out_path)
    return out_path, api_log
