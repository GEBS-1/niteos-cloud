# -*- coding: utf-8 -*-
"""Chat persistence and instruction parsing for Vision Agent Studio."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def agent_chat_path(base: Path) -> Path:
    return base / "agent_chat.jsonl"


def agent_state_path(base: Path) -> Path:
    return base / "agent_state.json"


def read_agent_state(base: Path) -> dict:
    path = agent_state_path(base)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_agent_state(base: Path, patch: dict) -> dict:
    state = read_agent_state(base)
    state.update(patch or {})
    state["updated_at"] = now_iso()
    agent_state_path(base).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return state


def append_chat_message(base: Path, role: str, text: str, **extra) -> dict:
    entry = {
        "ts": now_iso(),
        "role": role,
        "text": (text or "").strip(),
        **extra,
    }
    path = agent_chat_path(base)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_chat_history(base: Path, limit: int = 100) -> list[dict]:
    path = agent_chat_path(base)
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    if limit > 0:
        return rows[-limit:]
    return rows


def wants_place_fixture(message: str) -> bool:
    """True when user asks to place/add a luminaire in a marked zone."""
    low = (message or "").strip().lower()
    if not low:
        return False
    # Russian stems via unicode escapes (Windows-safe).
    keys = (
        "\u043f\u0440\u043e\u0441\u0442\u0430\u0432",  # prostav
        "\u043f\u043e\u0441\u0442\u0430\u0432",  # postav
        "\u0434\u043e\u0431\u0430\u0432",  # dobav
        "\u0440\u0430\u0437\u043c\u0435\u0441\u0442",  # razmest
        "\u0443\u0441\u0442\u0430\u043d\u043e\u0432",  # ustanov
        "place",
        "add light",
        "add fixture",
        "put a",
        "install",
        "projector",
        "\u043f\u0440\u043e\u0436\u0435\u043a\u0442",  # prozekt
        "\u0441\u0432\u0435\u0442\u0438\u043b\u044c\u043d",  # svetil'n
    )
    # Avoid false positive: "добавь тепла" without fixture verbs alone is warmer — still ok if place+mark.
    return any(k in low for k in keys)


def parse_chat_intent(message: str) -> dict:
    """Lightweight RU/EN intent parser for studio chat revisions."""
    text = (message or "").strip()
    low = text.lower()
    intent = {
        "action": "revise",
        "temperature": "",
        "remove_verticals": False,
        "boost_cornice": False,
        "boost_entrance": False,
        "warmer": False,
        "cooler": False,
        "regenerate": False,
        "place_fixture": False,
        "raw": text,
    }
    # Russian keywords via unicode escapes to avoid encoding issues on Windows.
    warmer_ru = "\u0442\u0435\u043f\u043b"  # tepl
    cooler_ru = "\u0445\u043e\u043b\u043e\u0434"  # holod
    vertical_ru = "\u0432\u0435\u0440\u0442\u0438\u043a"  # vertikal
    remove_ru = "\u0443\u0431\u0435\u0440"  # uber
    cornice_ru = "\u043a\u0430\u0440\u043d\u0438\u0437"  # karniz
    contour_ru = "\u043a\u043e\u043d\u0442\u0443\u0440"  # kontur
    regen_ru = "\u043f\u0435\u0440\u0435\u0433\u0435\u043d\u0435\u0440"  # peregener
    entrance_ru = "\u0432\u0445\u043e\u0434"  # vhod
    portal_ru = "\u043f\u043e\u0440\u0442\u0430\u043b"  # portal

    if any(w in low for w in (regen_ru, "regenerate", "restart", "\u0437\u0430\u043d\u043e\u0432\u043e")):
        intent["regenerate"] = True
        intent["action"] = "regenerate"
    if any(w in low for w in (warmer_ru, "warm", "3000", "2700")):
        intent["warmer"] = True
        intent["temperature"] = "3000K"
    if any(w in low for w in (cooler_ru, "cool", "4000", "5000", "\u043d\u0435\u0439\u0442\u0440\u0430\u043b")):
        intent["cooler"] = True
        intent["temperature"] = "4000K" if "4000" in low else "5000K"
    if vertical_ru in low and (remove_ru in low or "without" in low or "no " in low or "\u0431\u0435\u0437" in low):
        intent["remove_verticals"] = True
    if "remove vertical" in low or "no vertical" in low:
        intent["remove_verticals"] = True
    if any(w in low for w in (cornice_ru, contour_ru, "cornice", "contour")):
        intent["boost_cornice"] = True
    if any(w in low for w in (entrance_ru, portal_ru, "entrance", "portal")):
        intent["boost_entrance"] = True
    if wants_place_fixture(text):
        intent["place_fixture"] = True
    return intent


def intent_to_revision_prompt(
    intent: dict,
    state: dict,
    *,
    has_markup: bool = False,
    markup_mode: str = "",
) -> str:
    bits = []
    raw = (intent.get("raw") or "").strip()
    place = bool(intent.get("place_fixture")) or wants_place_fixture(raw)
    # With paint markup, never expand into global scheme changes.
    if has_markup:
        mode = (markup_mode or "").strip().lower()
        if mode == "remove":
            bits.append(
                "LOCAL EDIT ONLY from paint marks: CYAN marks = REMOVE those luminaires and their beams. "
                "Do NOT remove, dim, move, or redesign any luminaire without cyan paint on it. "
                "Copy every unmarked fixture and beam from Image 1 unchanged."
            )
        elif mode == "change" and place:
            bits.append(
                "LOCAL PLACE/ADD from RED paint marks: install the requested architectural luminaire "
                "(e.g. projector / linear / uplight) ONLY inside the red-marked zone(s), with a realistic beam. "
                "Do NOT invent fixtures outside red marks. Do NOT remove or redesign unmarked luminaires — "
                "copy them from Image 1 unchanged. Do not invent new architecture (pilasters/columns)."
            )
        elif mode == "change":
            bits.append(
                "LOCAL EDIT ONLY from paint marks: RED marks = CHANGE/REWORK those luminaires or beams "
                "(or, if the user asks to place/add, ADD a fixture only inside the red zone). "
                "Do NOT remove or redesign any luminaire without red paint on it. "
                "Copy every unmarked fixture and beam from Image 1 unchanged."
            )
        elif mode == "mixed" and place:
            bits.append(
                "LOCAL EDIT from paint: CYAN = remove those fixtures+beams; "
                "RED = place/add or change fixtures as the user asks, only inside red marks. "
                "Unmarked luminaires stay identical to Image 1."
            )
        else:
            bits.append(
                "LOCAL EDIT ONLY from paint marks: "
                "CYAN = remove that fixture+beam; RED = change that fixture+beam "
                "(or place/add a fixture in the red zone if the user asks). "
                "Do NOT touch any luminaire that has no paint on it — copy them from Image 1 unchanged."
            )
        if raw:
            bits.append(f"User request (apply only to marked zones): {raw}")
        bits.append("Never darken facade panels. Preserve building identity 1:1.")
        return " ".join(bits)

    if intent.get("temperature"):
        bits.append(f"Color temperature: {intent['temperature']}.")
    if intent.get("warmer"):
        bits.append("Make facade lighting warmer and softer.")
    if intent.get("cooler"):
        bits.append("Make facade lighting cooler/neutral white.")
    if intent.get("remove_verticals"):
        bits.append("Remove vertical projector accents; keep only horizontal/contour lines.")
    if intent.get("boost_cornice"):
        bits.append("Strengthen continuous cornice/contour lines; no gaps.")
    if intent.get("boost_entrance"):
        bits.append("Brighten entrance/portal accent carefully without reshaping architecture.")
    if place:
        bits.append("If user asks to place a fixture without marks, keep placement minimal and realistic.")
    if raw:
        bits.append(f"User request: {raw}")
    cluster = (state.get("scheme") or {}).get("cluster") or ""
    if cluster:
        bits.append(f"Keep lighting family: {cluster}.")
    bits.append("Preserve building identity 1:1; no new pilasters; keep signs.")
    return " ".join(bits)


STUDIO_MARKUP_CONTRACT = (
    "Image 1 = clean current night render (materials/geometry AND all luminaires source of truth). "
    "Image 2 = the SAME render with user paint composited on top (marks show WHERE to edit). "
    "HARD RULE for unmarked areas: every unmarked luminaire/beam stays identical to Image 1 — "
    "no global rebalancing, no removing 'extra' lights. "
    "Color semantics: "
    "1) RED / orange = CHANGE an existing luminaire under the mark, OR PLACE/ADD a new architectural "
    "luminaire (projector, linear, uplight, wash) ONLY inside the red zone when the user asks to "
    "place/install/add one — with a realistic beam matching neighboring lights. "
    "2) CYAN / aqua / blue = REMOVE only the marked luminaire(s) and their beams; "
    "after removal restore wall material like neighboring unmarked panels (NOT darker/black). "
    "FORBIDDEN: fixtures outside marks, new architecture, darkening cladding, keeping paint in output. "
)
