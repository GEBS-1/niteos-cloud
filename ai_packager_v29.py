from pathlib import Path
import os
import sys
import re
import shutil
import subprocess
from datetime import datetime
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance


def app_base_dir() -> Path:
    """
    В обычном запуске база — папка .py файла.
    В собранном .exe база — папка рядом с exe, чтобы input/ies/output/project_export
    создавались рядом с программой, а не во временной папке PyInstaller.
    """
    override = os.environ.get("NITEOS_BASE_DIR", "").strip()
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_base_dir()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
IES_DIR = BASE_DIR / "ies_library"
EXPORT_ROOT = BASE_DIR / "project_export"
REFERENCES_DIR = BASE_DIR / "references"
PROMPT_PATH = BASE_DIR / "prompt.txt"
MODE_PATH = BASE_DIR / "facade_mode.txt"

for d in (INPUT_DIR, OUTPUT_DIR, IES_DIR, EXPORT_ROOT, REFERENCES_DIR):
    d.mkdir(exist_ok=True)


@dataclass
class IesInfo:
    file_name: str
    stem: str
    kind: str
    lumens: float | None
    power: float | None
    lumcat: str = ""
    beam_hint: str = ""
    mount_hint: str = ""
    forbid_hint: str = ""


# ---------------------------------------------------------------------
# IES
# ---------------------------------------------------------------------

def read_text_any_encoding(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(enc, errors="ignore")
        except Exception:
            pass
    return data.decode("latin-1", errors="ignore")


def parse_float(value: str):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def parse_ies_lumcat(path: Path) -> str:
    text = read_text_any_encoding(path)
    for raw in text.splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("[LUMCAT]"):
            val = line.split("]", 1)[-1].strip()
            if val and not re.fullmatch(r"[\d\s/\[\]]+", val):
                return val
        if upper.startswith("[LUMINAIRE]"):
            val = line.split("]", 1)[-1].strip()
            if val and not re.fullmatch(r"[\d\s/\[\]]+", val):
                return val
    return path.stem.replace("_", " ")


def ies_photometry_hints(path: Path, kind: str) -> tuple[str, str, str]:
    """beam_hint, mount_hint, forbid_hint — визуальные правила по IES/имени файла."""
    name = f"{path.name} {path.stem} {kind}".upper()
    blob = name.replace("_", " ")

    if "МАГИСТРАЛЬ" in blob or "MAGISTRAL" in blob or "КОНСОЛЬ" in blob:
        return (
            "линейная КСС Д: тонкая непрерывная полоса света вдоль монтажной линии, без круглых пятен",
            "консольный линейный светильник на фасаде; корпус скрыт, видна только линия света",
            "прожекторные конусы, точечные споты, широкая заливка фасада, парковые столбы",
        )
    if "NT-WAY" in blob or "NT WAY" in blob or "Г61" in blob or "G61" in blob:
        return (
            "КСС Г61: направленная заливка/грайзинг фасада, мягкий конус от корпуса к плоскости стены",
            "компактный фасадный прожектор в нише/на кронштейне; корпус как на product front",
            "LED-линейные полосы, непрерывные контурные линии MAGISTRAL, парковые столбы",
        )
    if "NT-STEP" in blob or "NT STEP" in blob or "PARK" in blob:
        return (
            "КСС Д120 в столбе: крупное мягкое пятно на земле/дороге, лёгкий отблеск на цоколь",
            "наземный парковый столб на тротуаре перед зданием, НЕ на фасаде",
            "светильники на стене, LED-линии на фасаде, прожекторы на здании",
        )
    if "линей" in kind.lower() or "ксс д" in kind.lower():
        return (
            "линейная КСС: непрерывная полоса вдоль архитектурной линии",
            "линейный светильник вдоль карниза/пояса/простенка",
            "точечные прожекторы и круглые пятна",
        )
    if "широк" in kind.lower() or "залив" in kind.lower():
        return (
            "широкая КСС: мягкая заливка плоскости фасада",
            "фасадный прожектор, направленный на стену",
            "тонкие LED-линии и контурные полосы",
        )
    if "узк" in kind.lower() or "к10" in kind.lower() or "к20" in kind.lower():
        return (
            "узкая/акцентная КСС: направленный луч по стойке или ребру",
            "акцентный прожектор у основания колонны или простенка",
            "сплошная заливка всего фасада",
        )
    return (
        "свет по характеру загруженной IES-фотометрии",
        "светильник соответствует product front и IES-файлу",
        "типы света, не соответствующие загруженной IES",
    )


def parse_ies_metadata(path: Path):
    text = read_text_any_encoding(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    lumens = None
    power = None

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:W|Вт|ВТ)", path.stem, re.IGNORECASE)
    if m:
        power = parse_float(m.group(1))

    tilt_index = None
    for i, line in enumerate(lines):
        if line.upper().startswith("TILT="):
            tilt_index = i
            break

    if tilt_index is not None and tilt_index + 1 < len(lines):
        nums = lines[tilt_index + 1].replace(",", ".").split()
        if len(nums) >= 3:
            lamps = parse_float(nums[0])
            lumens_per_lamp = parse_float(nums[1])
            multiplier = parse_float(nums[2])
            if lamps is not None and lumens_per_lamp is not None and multiplier is not None:
                lumens = lamps * lumens_per_lamp * multiplier

        if power is None and tilt_index + 2 < len(lines):
            nums2 = lines[tilt_index + 2].replace(",", ".").split()
            if len(nums2) >= 3:
                maybe_power = parse_float(nums2[2])
                if maybe_power is not None and 0 < maybe_power < 10000:
                    power = maybe_power

    return lumens, power



def has_linear_d_kss(name_upper: str) -> bool:
    """
    КСС Д / Д120 — линейная КСС, но НЕ контурная.
    """
    n = " " + name_upper.replace("_", " ").replace("-", " ").replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ") + " "

    if "КСС Д" in n or " КССД " in n:
        return True

    # Кириллица: Д, Д120, Д 120 отдельным обозначением.
    if re.search(r"(^|[\s])Д\s*\d{0,3}($|[\s])", n):
        return True

    # Латиница: D / D120 отдельным токеном. Не ловим LED.
    if re.search(r"(^|[\s])D\s*\d{0,3}($|[\s])", n):
        return True

    return False



def classify_ies(path: Path) -> str:
    name = path.stem.upper()

    if "К10" in name or "K10" in name:
        return "узкий луч / К10"
    if "К20" in name or "K20" in name:
        return "средний луч / К20"
    if "Г60" in name or "G60" in name:
        return "широкая заливка / Г60"
    if "Г40" in name or "G40" in name:
        return "широкая заливка / Г40"

    # NT-WAY — заливающие / wall-washer серии NITEOS.
    if "NT-WAY" in name or "NT WAY" in name.replace("_", " "):
        return "широкая заливка / NT-WAY"

    # Д / Д120 — линейная КСС, не контурная.
    if has_linear_d_kss(name):
        m = re.search(r"Д\s*(\d{1,3})", name)
        if m:
            return f"линейная КСС Д{m.group(1)}"
        m = re.search(r"(^|[\s_\-])D\s*(\d{1,3})($|[\s_\-])", name)
        if m:
            return f"линейная КСС D{m.group(2)}"
        return "линейная КСС Д"

    # M260 / CONTOUR — контурная КСС.
    if "M260" in name or "М260" in name:
        return "контурная КСС M260"
    if "CONTOUR" in name or "КОНТУР" in name:
        return "контурная КСС"

    if "SLIM" in name:
        return "линейный светильник / КСС не определена"

    if "МАГИСТРАЛЬ" in name or "MAGISTRAL" in name:
        return "линейная КСС Д / MAGISTRAL консоль"

    if "NT-STEP" in name or "NT STEP" in name.replace("_", " "):
        return "парковый столб NT-STEP / КСС Д120"

    return "не определено"


def load_ies_infos_from_dir(ies_dir: Path) -> list[IesInfo]:
    if not ies_dir.exists():
        return []
    all_files = list(ies_dir.glob("*.ies")) + list(ies_dir.glob("*.IES"))
    result = []
    seen = set()
    for path in sorted(all_files, key=lambda p: p.name.lower()):
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        lumens, power = parse_ies_metadata(path)
        kind = classify_ies(path)
        beam, mount, forbid = ies_photometry_hints(path, kind)
        result.append(
            IesInfo(
                file_name=path.name,
                stem=path.stem,
                kind=kind,
                lumens=lumens,
                power=power,
                lumcat=parse_ies_lumcat(path),
                beam_hint=beam,
                mount_hint=mount,
                forbid_hint=forbid,
            )
        )
    return result


def load_ies_infos():
    return load_ies_infos_from_dir(IES_DIR)


def analyze_ies_capabilities(ies_infos):
    """
    Разделяем линейную КСС Д и контурную КСС M260/CONTOUR.
    """
    caps = {
        "has_ies": bool(ies_infos),
        "has_linear": False,
        "has_contour": False,
        "has_narrow": False,
        "has_wide": False,
        "has_unknown": False,
        "has_ground_pole": False,
        "mode": "visual_no_ies",
        "summary": "IES не загружены",
    }

    if not ies_infos:
        caps.update({
            "has_linear": True,
            "has_contour": True,
            "has_narrow": True,
            "has_wide": True,
            "mode": "visual_no_ies",
            "summary": "Визуальный режим без IES",
        })
        return caps

    for info in ies_infos:
        text = f"{info.file_name} {info.stem} {info.kind}".lower()

        if "nt-step" in text or "nt step" in text or "nt-park" in text or "nt park" in text:
            caps["has_ground_pole"] = True
            continue

        linear = (
            "линейная ксс д" in text
            or "линейная ксс d" in text
            or " ксс д" in text
        )
        contour = (
            "контурная ксс" in text
            or "контур" in text
            or "contour" in text
            or "m260" in text
            or "м260" in text
        )
        narrow = (
            "узкий" in text
            or "средний луч" in text
            or "k10" in text
            or "к10" in text
            or "k20" in text
            or "к20" in text
            or "uno line" in text
        )
        wide = (
            "широк" in text
            or "залив" in text
            or "g60" in text
            or "г60" in text
            or "g40" in text
            or "г40" in text
        )

        if linear:
            caps["has_linear"] = True
        elif contour:
            caps["has_contour"] = True
        elif narrow:
            caps["has_narrow"] = True
        elif wide:
            caps["has_wide"] = True
        else:
            caps["has_unknown"] = True

    line_only = (caps["has_linear"] or caps["has_contour"]) and not caps["has_narrow"] and not caps["has_wide"]

    if caps.get("has_ground_pole"):
        caps["mode"] = "ground_pole"
        caps["summary"] = "Загружен IES паркового столба NT-STEP"
    elif line_only:
        caps["mode"] = "line_only"
        if caps["has_linear"] and not caps["has_contour"]:
            caps["summary"] = "Загружены только линейные IES / КСС Д"
        elif caps["has_contour"] and not caps["has_linear"]:
            caps["summary"] = "Загружены только контурные IES / M260"
        else:
            caps["summary"] = "Загружены только линейные / контурные IES"
    elif caps["has_narrow"] and not caps["has_linear"] and not caps["has_contour"] and not caps["has_wide"]:
        caps["mode"] = "accent_only"
        caps["summary"] = "Загружены только акцентные / лучевые IES"
    elif caps["has_wide"] and not caps["has_linear"] and not caps["has_contour"] and not caps["has_narrow"]:
        caps["mode"] = "wide_only"
        caps["summary"] = "Загружены только заливающие IES"
    else:
        caps["mode"] = "mixed"
        caps["summary"] = "Загружен смешанный набор IES"

    return caps


def ies_recommendations_for_summary(ies_infos):
    caps = analyze_ies_capabilities(ies_infos)
    lines = []

    if not caps["has_ies"]:
        lines.append("- IES не загружены: работаем как с предварительной визуальной концепцией.")
        lines.append("- Не указывать точные модели, мощности, потоки и КСС.")
        return lines

    if caps["mode"] == "line_only":
        if caps["has_linear"] and not caps["has_contour"]:
            lines.append("- В загруженных IES есть только линейная КСС Д.")
            lines.append("- Использовать как линейную подсветку по рядам, поясам, ребрам и архитектурным членениям фасада.")
            lines.append("- Не называть эту КСС контурной и не рисовать прожекторные лучи/широкую заливку.")
        elif caps["has_contour"] and not caps["has_linear"]:
            lines.append("- В загруженных IES есть только контурная КСС M260/CONTOUR.")
            lines.append("- Использовать как контурную подсветку по карнизам, ребрам, контуру и линиям фасада.")
            lines.append("- Не рисовать прожекторные лучи и широкую заливку.")
        else:
            lines.append("- В загруженных IES есть только линейные/контурные КСС.")
            lines.append("- Использовать только линейную подсветку по архитектурным линиям фасада.")
            lines.append("- Не рисовать прожекторные лучи и широкую заливку.")
        return lines

    if caps["has_linear"]:
        lines.append("- КСС Д использовать как линейную подсветку по рядам, поясам, ребрам и членениям фасада.")
    if caps["has_contour"]:
        lines.append("- M260/CONTOUR использовать как контурную подсветку по карнизам, ребрам и контуру.")
    if caps["has_narrow"]:
        lines.append("- К10/К20/акцентные IES использовать как направленные лучи по стойкам, простенкам и ребрам.")
    if caps["has_wide"]:
        lines.append("- Г40/Г60/широкую КСС использовать как мягкую заливающую подсветку.")
    if caps["has_unknown"]:
        lines.append("- Часть IES не удалось классифицировать: использовать осторожно, без точной световой роли.")

    lines.append("- Цветовая температура света — согласно заданию пользователя.")
    return lines




def build_ies_summary(ies_infos):
    lines = []
    lines.append("IES-СВОДКА ДЛЯ КОНЦЕПЦИИ")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Назначение:")
    lines.append("Этот файл нужен не для точного расчета DIALux, а для привязки AI-концепции к реальным светильникам.")
    lines.append("Финальный светотехнический расчет должен выполнить светодизайнер в DIALux/Relux.")
    lines.append("")

    if not ies_infos:
        lines.append("IES-файлы не найдены в папке ies_library.")
        return "\n".join(lines)

    total_power_one_each = 0.0

    lines.append("Найденные IES-файлы:")
    lines.append("")

    for i, info in enumerate(ies_infos, start=1):
        power_text = f"{info.power:g} Вт" if info.power is not None else "не определено"
        lumens_text = f"{info.lumens:g} лм" if info.lumens is not None else "не определено"

        if info.power is not None:
            total_power_one_each += info.power

        lines.append(f"{i}. {info.stem}")
        lines.append(f"   Файл: {info.file_name}")
        lines.append(f"   Тип света: {info.kind}")
        lines.append(f"   Мощность: {power_text}")
        lines.append(f"   Световой поток: {lumens_text}")
        lines.append("")

    lines.append("Рекомендации для AI:")
    for rec in ies_recommendations_for_summary(ies_infos):
        lines.append(rec)
    lines.append("")
    lines.append(f"Суммарная мощность одного комплекта найденных IES: примерно {total_power_one_each:g} Вт")
    lines.append("Фактическая суммарная мощность зависит от количества светильников в принятой концепции.")

    return "\n".join(lines)


def build_equipment_draft(ies_infos):
    lines = []
    lines.append("ПРЕДВАРИТЕЛЬНАЯ ВЕДОМОСТЬ ДЛЯ КОНЦЕПЦИИ")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Внимание: количество и мощности предварительные. Финально уточняет светодизайнер после расчета.")
    lines.append("")

    if not ies_infos:
        lines.append("Ведомость оборудования не сформирована — IES-файлы не загружены.")
        lines.append("")
        lines.append("Режим проекта: визуальная концепция без привязки к конкретным светильникам.")
        lines.append("На этом этапе можно согласовать световую идею с заказчиком.")
        lines.append("После согласования нужно загрузить IES-файлы и выполнить подбор оборудования / расчет в DIALux или Relux.")
        return "\n".join(lines)

    narrow = [x for x in ies_infos if "К10" in x.kind or "узкий" in x.kind.lower()]
    line = [x for x in ies_infos if "контур" in x.kind.lower() or "линей" in x.kind.lower()]
    wide = [x for x in ies_infos if "широк" in x.kind.lower() or "Г60" in x.kind]

    rows = []

    if line:
        rows.append(("Контурная линия по основным карнизам / ребрам фасада", line[0], "~20 м", "Предварительно по верхним горизонтальным линиям фасада"))
    if narrow:
        rows.append(("Узкие вертикальные акценты", narrow[0], "~8 шт.", "По стойкам, простенкам, пилястрам или фасадным членениям"))
    if wide:
        rows.append(("Мягкая заливка входной группы / нижнего яруса", wide[0], "~3 зоны", "Вход, витражи, нижний уровень, акцентные зоны"))

    if not rows:
        rows.append(("Основная архитектурная подсветка", ies_infos[0], "уточнить", "Предварительная концепция"))

    lines.append("| № | Тип подсветки | IES / модель | Мощность | Поток | Кол-во | Примечание |")
    lines.append("|---|---|---|---:|---:|---:|---|")

    for idx, (kind, info, qty, note) in enumerate(rows, start=1):
        power_text = f"{info.power:g} Вт" if info.power is not None else "—"
        lumens_text = f"{info.lumens:g} лм" if info.lumens is not None else "—"
        lines.append(f"| {idx} | {kind} | {info.stem} | {power_text} | {lumens_text} | {qty} | {note} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Images / light plan
# ---------------------------------------------------------------------

def find_source_image() -> Path:
    if (INPUT_DIR / "building.png").exists():
        return INPUT_DIR / "building.png"

    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.PNG", "*.JPG", "*.JPEG", "*.WEBP"):
        files = list(INPUT_DIR.glob(pattern))
        if files:
            return files[0]

    raise FileNotFoundError("В папке input нет изображения фасада.")


def safe_copy_image(src: Path, dst: Path):
    img = Image.open(src).convert("RGB")
    img.save(dst, quality=95)


def make_night_base(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")

    dark = ImageEnhance.Brightness(img).enhance(0.34)
    dark = ImageEnhance.Color(dark).enhance(0.62)
    dark = ImageEnhance.Contrast(dark).enhance(1.06)

    cool = Image.new("RGB", img.size, (6, 8, 12))
    night = Image.blend(dark, cool, 0.28)

    return night.convert("RGBA")


def draw_glow_line(base: Image.Image, p1, p2, intensity=1.0):
    # Теплый свет, но в reference не слишком яркий.
    color = (255, 185, 94)
    w, h = base.size

    for width, alpha, blur in [
        (18, int(22 * intensity), 16),
        (10, int(38 * intensity), 8),
        (4, int(86 * intensity), 3),
        (2, int(190 * intensity), 0),
    ]:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([p1, p2], fill=(color[0], color[1], color[2], alpha), width=width)
        if blur > 0:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        base = Image.alpha_composite(base, layer)

    return base


def draw_uplight(base: Image.Image, x: int, y: int, bbox, intensity=1.0):
    color = (255, 185, 94)
    w, h = base.size
    x0, y0, x1, y1 = bbox
    fh = y1 - y0

    beam_h = int(fh * 0.54)
    base_w = max(5, int(w * 0.010))
    top_w = max(14, int(w * 0.026))
    top_y = max(y0 + int(fh * 0.08), y - beam_h)

    outer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(outer)
    d.polygon(
        [(x - base_w, y), (x + base_w, y), (x + top_w, top_y), (x - top_w, top_y)],
        fill=(color[0], color[1], color[2], int(25 * intensity)),
    )
    outer = outer.filter(ImageFilter.GaussianBlur(18))
    base = Image.alpha_composite(base, outer)

    inner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(inner)
    d.polygon(
        [
            (x - int(base_w * 0.50), y),
            (x + int(base_w * 0.50), y),
            (x + int(top_w * 0.25), top_y),
            (x - int(top_w * 0.25), top_y),
        ],
        fill=(255, 210, 130, int(43 * intensity)),
    )
    inner = inner.filter(ImageFilter.GaussianBlur(9))
    base = Image.alpha_composite(base, inner)

    return base


def draw_soft_zone(base: Image.Image, cx: int, cy: int, rx: int, ry: int, intensity=1.0):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        fill=(255, 185, 94, int(23 * intensity)),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(12, int(min(rx, ry) * 0.55))))
    return Image.alpha_composite(base, layer)



def parse_light_intent(user_prompt: str):
    """
    Простая логика понимания задания:
    - если пользователь просит флаг России / белый-синий-красный по зонам,
      reference строится как зоны света, а не как случайные линии здания;
    - если цветового задания нет, используется нейтральная архитектурная схема.
    """
    low = (user_prompt or "").lower()

    is_russian_flag = (
        "флаг россии" in low
        or "триколор" in low
        or ("бел" in low and "син" in low and "крас" in low)
    )

    def color_tuple(name):
        if name == "white":
            return (240, 245, 255)
        if name == "blue":
            return (45, 115, 255)
        if name == "red":
            return (255, 55, 42)
        return (255, 185, 94)

    if is_russian_flag:
        return {
            "mode": "russian_flag",
            "top": color_tuple("white"),
            "middle": color_tuple("blue"),
            "bottom": color_tuple("red"),
            "use_contour_line": False,
            "description": "верх — белый, середина — синий, низ — красный, как флаг России",
        }

    # Иначе пытаемся понять отдельные цвета.
    top = color_tuple("warm")
    middle = color_tuple("warm")
    bottom = color_tuple("warm")

    if "син" in low:
        middle = color_tuple("blue")
    if "крас" in low:
        bottom = color_tuple("red")
    if "бел" in low or "4000" in low or "5000" in low:
        top = color_tuple("white")

    return {
        "mode": "default",
        "top": top,
        "middle": middle,
        "bottom": bottom,
        "use_contour_line": any(x in low for x in ["контур", "карниз", "линия", "линейн"]),
        "description": "общая архитектурная подсветка по заданию пользователя",
    }


def draw_soft_band(base: Image.Image, y: int, x0: int, x1: int, height: int, color, intensity=1.0):
    """
    Мягкая горизонтальная зона света без жесткой технической линии.
    Так AI меньше копирует кривые линии из reference.
    """
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    alpha = int(36 * intensity)
    d.rounded_rectangle(
        [x0, max(0, y - height // 2), x1, min(h, y + height // 2)],
        radius=max(8, height // 3),
        fill=(color[0], color[1], color[2], alpha),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(14, height // 2)))
    return Image.alpha_composite(base, layer)



def draw_atmospheric_zone(base: Image.Image, rect, color, intensity=1.0, blur_scale=0.16):
    """
    Видимая, но мягкая зона света для light plan reference.
    Не чертежная линия, а понятная подсказка для AI.
    """
    w, h = base.size
    x0, y0, x1, y1 = rect
    zone_w = max(1, x1 - x0)
    zone_h = max(1, y1 - y0)

    # Большое мягкое пятно
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    d.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=max(18, zone_h // 3),
        fill=(color[0], color[1], color[2], int(62 * intensity)),
    )

    blur = max(10, int(min(zone_w, zone_h) * blur_scale))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base = Image.alpha_composite(base, layer)

    # Внутренняя зона, чтобы карта не выглядела пустой
    inner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(inner)
    pad_x = int(zone_w * 0.05)
    pad_y = int(zone_h * 0.20)
    d.rounded_rectangle(
        [x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y],
        radius=max(12, zone_h // 5),
        fill=(color[0], color[1], color[2], int(38 * intensity)),
    )
    inner = inner.filter(ImageFilter.GaussianBlur(max(8, blur // 2)))
    return Image.alpha_composite(base, inner)


def draw_soft_vertical_accent(base: Image.Image, x: int, y0: int, y1: int, color, intensity=1.0):
    """
    Вертикальный акцент заметный на карте, но без жесткого лазера.
    """
    w, h = base.size
    height = max(1, y1 - y0)
    beam_w = max(8, int(w * 0.010))
    top_w = max(20, int(w * 0.030))

    # широкое мягкое свечение
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon(
        [(x - beam_w, y1), (x + beam_w, y1), (x + top_w, y0), (x - top_w, y0)],
        fill=(color[0], color[1], color[2], int(78 * intensity)),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(8, int(height * 0.035))))
    base = Image.alpha_composite(base, layer)

    # ядро луча
    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(core)
    d.polygon(
        [
            (x - max(3, beam_w // 3), y1),
            (x + max(3, beam_w // 3), y1),
            (x + max(6, top_w // 5), y0),
            (x - max(6, top_w // 5), y0),
        ],
        fill=(color[0], color[1], color[2], int(68 * intensity)),
    )
    core = core.filter(ImageFilter.GaussianBlur(5))
    return Image.alpha_composite(base, core)



def draw_soft_pool(base: Image.Image, cx: int, cy: int, rx: int, ry: int, color, intensity=1.0):
    """
    Мягкое пятно заливки. Для нижнего красного света лучше, чем сплошная полоса.
    """
    w, h = base.size

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        fill=(color[0], color[1], color[2], int(58 * intensity)),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(10, int(min(rx, ry) * 0.50))))
    base = Image.alpha_composite(base, layer)

    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(core)
    d.ellipse(
        [cx - int(rx * 0.55), cy - int(ry * 0.45), cx + int(rx * 0.55), cy + int(ry * 0.45)],
        fill=(color[0], color[1], color[2], int(30 * intensity)),
    )
    core = core.filter(ImageFilter.GaussianBlur(max(7, int(min(rx, ry) * 0.35))))
    return Image.alpha_composite(base, core)



def draw_soft_horizontal_glow(base: Image.Image, p1, p2, color, intensity=1.0):
    """
    Световой край/контур, более видимый чем зона, но не тонкая чертежная линия.
    """
    w, h = base.size
    for width, alpha, blur in [
        (18, int(40 * intensity), 12),
        (8, int(72 * intensity), 5),
        (3, int(130 * intensity), 1),
    ]:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([p1, p2], fill=(color[0], color[1], color[2], alpha), width=width)
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        base = Image.alpha_composite(base, layer)
    return base


def draw_soft_contour(base: Image.Image, p1, p2, color, intensity=1.0):
    """
    Тонкая контурная линия, но не как чертежная разметка.
    """
    w, h = base.size
    for width, alpha, blur in [
        (14, int(20 * intensity), 14),
        (7, int(42 * intensity), 7),
        (2, int(150 * intensity), 0),
    ]:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([p1, p2], fill=(color[0], color[1], color[2], alpha), width=width)
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        base = Image.alpha_composite(base, layer)
    return base


def draw_colored_uplight(base: Image.Image, x: int, y: int, bbox, color, intensity=1.0, beam_scale=1.0):
    w, h = base.size
    x0, y0, x1, y1 = bbox
    fh = y1 - y0

    beam_h = int(fh * 0.48 * beam_scale)
    base_w = max(5, int(w * 0.009))
    top_w = max(16, int(w * 0.022))
    top_y = max(y0 + int(fh * 0.16), y - beam_h)

    outer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(outer)
    d.polygon(
        [(x - base_w, y), (x + base_w, y), (x + top_w, top_y), (x - top_w, top_y)],
        fill=(color[0], color[1], color[2], int(30 * intensity)),
    )
    outer = outer.filter(ImageFilter.GaussianBlur(17))
    base = Image.alpha_composite(base, outer)

    inner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(inner)
    d.polygon(
        [
            (x - int(base_w * 0.55), y),
            (x + int(base_w * 0.55), y),
            (x + int(top_w * 0.28), top_y),
            (x - int(top_w * 0.28), top_y),
        ],
        fill=(color[0], color[1], color[2], int(48 * intensity)),
    )
    inner = inner.filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(base, inner)




def smooth_values(values, radius=3):
    if not values:
        return values
    out = []
    n = len(values)
    for i in range(n):
        a = max(0, i - radius)
        b = min(n, i + radius + 1)
        out.append(sum(values[a:b]) / max(1, b - a))
    return out


def median_value(values):
    if not values:
        return 0
    s = sorted(values)
    return s[len(s) // 2]


def largest_relevant_block(flags, prefer_center=True):
    """
    Возвращает самый полезный непрерывный блок True.
    Для фасадов обычно нужен большой центральный блок, а не дерево/фон по краям.
    """
    blocks = []
    start = None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            blocks.append((start, i - 1))
            start = None

    if not blocks:
        return None

    n = len(flags)
    center = n / 2

    def score(block):
        a, b = block
        width = b - a + 1
        mid = (a + b) / 2
        center_bonus = max(0, 1 - abs(mid - center) / max(1, center))
        # Ширина важнее всего, но центральность помогает отсечь деревья/фон.
        return width * (1.0 + 0.55 * center_bonus)

    return max(blocks, key=score)


def facade_column_span(col_scores, edge_trim_ratio=0.015, min_span_ratio=0.90):
    """
    Ширина рабочей зоны: от левого до правого фасадного блока в кадре.
    Низкий порог — чтобы не потерять боковые крылья и соседние секции здания.
    """
    if not col_scores:
        return None
    col_max = max(col_scores)
    if col_max <= 0:
        return None
    thr = max(col_max * 0.06, 1)
    xs = [i for i, v in enumerate(col_scores) if v >= thr]
    if not xs:
        return None
    n = len(col_scores)
    sx0 = max(0, xs[0] - int(n * edge_trim_ratio))
    sx1 = min(n - 1, xs[-1] + int(n * edge_trim_ratio))
    if (sx1 - sx0) < n * min_span_ratio:
        sx0 = int(n * 0.02)
        sx1 = int(n * 0.98)
    return sx0, sx1


def estimate_facade_bbox(img: Image.Image):
    """
    Грубая автоматическая оценка рабочей зоны фасада.
    По вертикали — не залезать в небо и дорогу.
    По горизонтали — почти вся ширина кадра, чтобы подсветка шла на всё здание.
    Работает без OpenCV, только PIL.
    """
    w, h = img.size

    # Безопасный fallback
    fallback = (int(w * 0.02), int(h * 0.12), int(w * 0.98), int(h * 0.90))

    try:
        small_w = 320
        small_h = max(160, int(h * small_w / max(1, w)))
        small = img.resize((small_w, small_h), Image.Resampling.BILINEAR).convert("L")
        edges = small.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.8))

        px = edges.load()

        # Ищем ряды с выраженной фасадной/оконной структурой.
        y_min_search = int(small_h * 0.08)
        y_max_search = int(small_h * 0.92)
        row_scores = []
        for y in range(small_h):
            if y < y_min_search or y > y_max_search:
                row_scores.append(0)
                continue
            s = 0
            for x in range(int(small_w * 0.03), int(small_w * 0.97)):
                v = px[x, y]
                if v > 18:
                    s += v
            row_scores.append(s)

        row_scores = smooth_values(row_scores, radius=3)
        row_med = median_value([v for v in row_scores[y_min_search:y_max_search] if v > 0])
        row_max = max(row_scores) if row_scores else 0
        row_thr = max(row_med * 1.35, row_max * 0.12, 1)

        row_flags = [v >= row_thr for v in row_scores]
        row_block = largest_relevant_block(row_flags)
        if not row_block:
            return fallback

        sy0, sy1 = row_block
        # Чуть расширяем рабочую зону по высоте.
        sy0 = max(y_min_search, sy0 - int(small_h * 0.035))
        sy1 = min(y_max_search, sy1 + int(small_h * 0.055))

        # Ищем колонки внутри найденного диапазона.
        col_scores = []
        for x in range(small_w):
            s = 0
            for y in range(sy0, sy1 + 1):
                v = px[x, y]
                if v > 18:
                    s += v
            col_scores.append(s)

        col_scores = smooth_values(col_scores, radius=4)
        col_span = facade_column_span(col_scores)
        if not col_span:
            return fallback

        sx0, sx1 = col_span

        # Перевод в исходный масштаб.
        x0 = int(sx0 / small_w * w)
        x1 = int(sx1 / small_w * w)
        y0 = int(sy0 / small_h * h)
        y1 = int(sy1 / small_h * h)

        # Защита от слишком маленькой/странной зоны по высоте.
        if (y1 - y0) < h * 0.25:
            return fallback

        # Горизонтально — почти весь кадр: все секции и крылья здания в кадре.
        x0 = int(w * 0.02)
        x1 = int(w * 0.98)

        # Нижнюю границу чуть ограничим: дорога/газон не должен быть основной зоной.
        y1 = min(y1, int(h * 0.90))

        # Верхнюю границу не поднимаем в небо слишком высоко.
        y0 = max(y0, int(h * 0.08))

        return (x0, y0, x1, y1)

    except Exception:
        return fallback


def draw_facade_area_outline(base: Image.Image, bbox, color=(210, 220, 235), alpha=0):
    # Сейчас рамку не рисуем, но функция оставлена для отладки.
    return base




def load_facade_mode():
    """
    Режим выбирается из GUI:
    - auto
    - modern_glass
    - classic
    """
    try:
        if MODE_PATH.exists():
            value = MODE_PATH.read_text(encoding="utf-8", errors="ignore").strip().lower()
            if value in {"auto", "modern_glass", "classic"}:
                return value
    except Exception:
        pass
    return "auto"


def is_modern_glass_prompt(user_prompt: str) -> bool:
    low = (user_prompt or "").lower()
    return any(word in low for word in ["стекл", "витраж", "офис", "бизнес", "кругл", "радиус", "современ", "панорам"])




def draw_modern_horizontal_band(base: Image.Image, x0: int, x1: int, y: int, color, intensity=1.0):
    """
    Для стеклянного фасада: тонкая мягкая линия по межэтажному поясу.
    Не широкая полоса по небу/деревьям.
    """
    w, h = base.size
    x0 = max(0, x0)
    x1 = min(w - 1, x1)
    y = max(0, min(h - 1, y))

    for width, alpha, blur in [
        (10, int(28 * intensity), 8),
        (4, int(52 * intensity), 3),
        (1, int(120 * intensity), 0),
    ]:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([(x0, y), (x1, y)], fill=(color[0], color[1], color[2], alpha), width=width)
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        base = Image.alpha_composite(base, layer)
    return base


def draw_modern_wall_washer(base: Image.Image, x: int, y0: int, y1: int, color, intensity=1.0):
    """
    Для стеклянного/офисного фасада: узкий мягкий акцент по стойке/вертикальному ребру.
    Намеренно слабее классического прожекторного луча.
    """
    w, h = base.size
    x = max(0, min(w - 1, x))
    y0 = max(0, min(h - 1, y0))
    y1 = max(0, min(h - 1, y1))
    if y1 <= y0:
        return base

    height = y1 - y0
    band_w = max(3, int(w * 0.004))
    glow_w = max(10, int(w * 0.012))

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        [x - glow_w, y0, x + glow_w, y1],
        radius=max(8, glow_w),
        fill=(color[0], color[1], color[2], int(30 * intensity)),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(6, int(height * 0.025))))
    base = Image.alpha_composite(base, layer)

    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(core)
    d.rounded_rectangle(
        [x - band_w, y0 + int(height * 0.05), x + band_w, y1 - int(height * 0.05)],
        radius=band_w,
        fill=(color[0], color[1], color[2], int(35 * intensity)),
    )
    core = core.filter(ImageFilter.GaussianBlur(3))
    return Image.alpha_composite(base, core)



def draw_ground_pole_map(base: Image.Image, bbox, color, user_prompt: str = ""):
    """Карта для NT-STEP: наземные столбы, пятна на дороге, без линий на фасаде."""
    x0, y0, x1, y1 = bbox
    fw = x1 - x0
    fh = y1 - y0
    low = (user_prompt or "").lower()
    count = 4
    if "редк" in low or "3" in low or "4" in low:
        count = 3
    if "вход" in low or "усил" in low:
        count = 6
    ground_y = int(y1 + fh * 0.06)
    xs = [int(x0 + fw * t) for t in [0.12, 0.28, 0.44, 0.60, 0.76, 0.90][:count]]
    for x in xs:
        pool_rx = max(28, int(fw * 0.045))
        pool_ry = max(16, int(fh * 0.035))
        base = draw_soft_pool(base, x, ground_y, pool_rx, pool_ry, color, intensity=0.55)
        base = draw_soft_vertical_accent(
            base, x, int(y1 - fh * 0.08), int(y1 + fh * 0.02), color, intensity=0.22
        )
    return base



def draw_contour_only_map(base: Image.Image, bbox, color, modern=False):
    """
    Карта света, если в проекте загружены только контурные / линейные IES.
    Никаких вертикальных прожекторных лучей.
    """
    x0, y0, x1, y1 = bbox
    fw = x1 - x0
    fh = y1 - y0

    if modern:
        x0 = int(x0 + fw * 0.02)
        x1 = int(x1 - fw * 0.02)
        y0 = int(y0 + fh * 0.03)
        y1 = int(y1 - fh * 0.04)
        fw = x1 - x0
        fh = y1 - y0

        band_positions = (0.17, 0.34, 0.51)
        for t in band_positions:
            y = int(y0 + fh * t)
            base = draw_modern_horizontal_band(base, int(x0 + fw * 0.01), int(x1 - fw * 0.01), y, color, intensity=0.70)

        # Мягкий верхний контур/ребро.
        base = draw_modern_horizontal_band(
            base,
            int(x0 + fw * 0.01),
            int(x1 - fw * 0.01),
            int(y0 + fh * 0.08),
            color,
            intensity=0.58,
        )
    else:
        hx0 = int(x0 + fw * 0.02)
        hx1 = int(x1 - fw * 0.02)
        for t in (0.10, 0.28, 0.48, 0.66):
            y = int(y0 + fh * t)
            base = draw_soft_horizontal_glow(base, (hx0, y), (hx1, y), color, intensity=0.62)

    return base



def draw_modern_glass_map(base: Image.Image, bbox, color, user_prompt: str, ies_caps=None):
    """
    Отдельная логика карты для современных стеклянных/радиусных фасадов.
    Главная идея: не рисовать классические широкие лучи и случайные полосы.
    """
    x0, y0, x1, y1 = bbox
    fw = x1 - x0
    fh = y1 - y0

    x0 = int(x0 + fw * 0.02)
    x1 = int(x1 - fw * 0.02)
    y0 = int(y0 + fh * 0.03)
    y1 = int(y1 - fh * 0.04)
    fw = x1 - x0
    fh = y1 - y0

    low = (user_prompt or "").lower()
    has_top_down = ("по верху" in low or "сверху" in low or ("верх" in low and "вниз" in low))
    is_bidirectional = ("верх-вниз" in low or "вверх-вниз" in low or "верх вниз" in low or "вверх вниз" in low or "двой" in low)

    ies_caps = ies_caps or analyze_ies_capabilities([])
    allow_contour = ies_caps.get("has_contour", True)
    allow_vertical = ies_caps.get("has_narrow", True)
    allow_fill = ies_caps.get("has_wide", True) or not ies_caps.get("has_ies", False)

    # 1) Межэтажные/горизонтальные пояса — только если есть контурные IES
    # или режим без IES.
    if allow_contour:
        band_ys = [int(y0 + fh * t) for t in (0.20, 0.38, 0.56)]
        for y in band_ys:
            base = draw_modern_horizontal_band(
                base,
                int(x0 + fw * 0.03),
                int(x1 - fw * 0.03),
                y,
                color,
                intensity=0.52,
            )

    # 2) Верхняя заливка вниз — не как туман по небу, а как слабая подсветка верхнего пояса.
    if has_top_down:
        top_band = (
            int(x0 + fw * 0.05),
            int(y0 + fh * 0.02),
            int(x1 - fw * 0.05),
            int(y0 + fh * 0.16),
        )
        base = draw_atmospheric_zone(base, top_band, color, intensity=0.16, blur_scale=0.18)

    # 3) Вертикальные стойки/ребра — только если есть акцентные / лучевые IES
    # или режим без IES. Если загружен только контур — не рисуем вертикальные лучи.
    if allow_vertical:
        x_positions = (0.12, 0.23, 0.34, 0.45, 0.56, 0.67, 0.78, 0.88)
        for t in x_positions:
            x = int(x0 + fw * t)
            if is_bidirectional:
                center = int(y0 + fh * 0.48)
                base = draw_modern_wall_washer(base, x, int(y0 + fh * 0.24), center, color, intensity=0.62)
                base = draw_modern_wall_washer(base, x, center, int(y0 + fh * 0.70), color, intensity=0.55)
            else:
                base = draw_modern_wall_washer(base, x, int(y0 + fh * 0.26), int(y0 + fh * 0.72), color, intensity=0.55)

    # 4) Нижний витражный уровень — только если есть заливающая КСС
    # или режим без IES.
    if allow_fill:
        lower = (
            int(x0 + fw * 0.06),
            int(y0 + fh * 0.72),
            int(x1 - fw * 0.06),
            int(y0 + fh * 0.86),
        )
        base = draw_atmospheric_zone(base, lower, color, intensity=0.10, blur_scale=0.22)

    return base



def generate_light_plan_reference(source_path: Path, out_path: Path, user_prompt: str = '', ies_infos=None):
    """
    Создает читаемую карту световых зон.
    v2.0:
    - режим "Современный стеклянный фасад" теперь действительно другой:
      тонкие пояса, стойки и мягкая нижняя зона вместо классических широких лучей;
    - классический режим работает по старой логике.
    """
    img = Image.open(source_path).convert("RGB")
    w, h = img.size

    base_rgb = img.convert("RGB")
    dark = ImageEnhance.Brightness(base_rgb).enhance(0.42)
    dark = ImageEnhance.Color(dark).enhance(0.55)
    dark = ImageEnhance.Contrast(dark).enhance(1.08)
    cool = Image.new("RGB", img.size, (4, 5, 7))
    base = Image.blend(dark, cool, 0.28).convert("RGBA")

    intent = parse_light_intent(user_prompt)
    low = (user_prompt or "").lower()
    facade_mode = load_facade_mode()

    is_flag = intent["mode"] == "russian_flag"
    is_bidirectional = ("верх-вниз" in low or "вверх-вниз" in low or "верх вниз" in low or "вверх вниз" in low or "двой" in low)
    has_brick_balcony_line = ("кирпич" in low and ("балкон" in low or "балко" in low))
    has_top_down = ("по верху" in low or "сверху" in low or ("верх" in low and "вниз" in low))

    if facade_mode == "modern_glass":
        is_modern_glass = True
    elif facade_mode == "classic":
        is_modern_glass = False
    else:
        is_modern_glass = is_modern_glass_prompt(user_prompt)

    bbox = estimate_facade_bbox(img)

    top_color = intent["top"]
    middle_color = intent["middle"]
    bottom_color = intent["bottom"]

    ies_caps = analyze_ies_capabilities(ies_infos or [])

    if ies_caps.get("mode") == "ground_pole":
        base = draw_ground_pole_map(base, bbox, top_color, user_prompt)
        base.convert("RGB").save(out_path, quality=95)
        return

    # Если загружены только контурные / линейные IES, черновик не имеет права
    # рисовать прожекторные вертикальные лучи и заливку.
    if ies_caps.get("mode") == "line_only":
        base = draw_contour_only_map(base, bbox, top_color, modern=is_modern_glass)
        base.convert("RGB").save(out_path, quality=95)
        return

    # Главная правка v2.1: современный стеклянный фасад уходит в отдельный сценарий.
    # Там не используются классические широкие прожекторные лучи.
    if is_modern_glass and not is_flag and "крас" not in low:
        base = draw_modern_glass_map(base, bbox, top_color, user_prompt, ies_caps=ies_caps)
        base.convert("RGB").save(out_path, quality=95)
        return

    # Ниже — классическая / универсальная логика.
    x0, y0, x1, y1 = bbox
    fw = x1 - x0
    fh = y1 - y0

    top_rect = (
        int(x0 + fw * 0.02),
        int(y0 + fh * 0.02),
        int(x1 - fw * 0.02),
        int(y0 + fh * (0.24 if has_top_down or is_flag else 0.20)),
    )
    base = draw_atmospheric_zone(base, top_rect, top_color, intensity=0.88 if has_top_down else 0.76, blur_scale=0.11)

    hx0 = int(x0 + fw * 0.02)
    hx1 = int(x1 - fw * 0.02)
    if ies_caps.get("has_contour") or ies_caps.get("has_narrow"):
        for t in (0.08, 0.22, 0.36, 0.50, 0.64, 0.78):
            y = int(y0 + fh * t)
            base = draw_soft_horizontal_glow(base, (hx0, y), (hx1, y), top_color, intensity=0.58)

    if has_top_down and (ies_caps.get("has_wide") or not ies_caps.get("has_ies")):
        top_down_y0 = int(y0 + fh * 0.05)
        top_down_y1 = int(y0 + fh * 0.32)
        xs_top = [int(x0 + fw * t) for t in (0.08, 0.18, 0.28, 0.38, 0.50, 0.62, 0.72, 0.82, 0.92)]
        for x in xs_top:
            base = draw_soft_vertical_accent(base, x, top_down_y0, top_down_y1, top_color, intensity=0.48)

    accent_top = int(y0 + fh * 0.20)
    accent_bottom = int(y0 + fh * 0.72)
    accent_center = int((accent_top + accent_bottom) / 2)
    xs = [int(x0 + fw * t) for t in (0.08, 0.18, 0.28, 0.38, 0.50, 0.62, 0.72, 0.82, 0.92)]

    if ies_caps.get("has_narrow") or not ies_caps.get("has_ies"):
        for x in xs:
            if is_bidirectional:
                base = draw_soft_vertical_accent(base, x, accent_top, accent_center, middle_color, intensity=0.62)
                base = draw_soft_vertical_accent(base, x, accent_center, accent_bottom, middle_color, intensity=0.62)
                base = draw_soft_pool(base, x, accent_center, max(8, int(fw * 0.010)), max(8, int(fh * 0.015)), middle_color, intensity=0.24)
            else:
                base = draw_soft_vertical_accent(base, x, accent_top, accent_bottom, middle_color, intensity=0.84 if is_flag else 0.72)

    if has_brick_balcony_line:
        line_y = int(y0 + fh * 0.66)
        base = draw_soft_horizontal_glow(
            base,
            (int(x0 + fw * 0.10), line_y),
            (int(x1 - fw * 0.10), line_y),
            top_color,
            intensity=0.50,
        )
        brick_up_rect = (
            int(x0 + fw * 0.10),
            int(line_y - fh * 0.12),
            int(x1 - fw * 0.10),
            int(line_y + fh * 0.05),
        )
        base = draw_atmospheric_zone(base, brick_up_rect, top_color, intensity=0.26, blur_scale=0.18)

    if is_flag or "крас" in low:
        bottom_y = int(y0 + fh * 0.86)
        pool_rx = max(30, int(fw * 0.055))
        pool_ry = max(14, int(fh * 0.040))
        for t in (0.11, 0.25, 0.40, 0.56, 0.72, 0.88):
            base = draw_soft_pool(base, int(x0 + fw * t), bottom_y, pool_rx, pool_ry, bottom_color, intensity=0.78)
    else:
        if ies_caps.get("has_wide") or not ies_caps.get("has_ies"):
            lower_rect = (
                int(x0 + fw * 0.08),
                int(y0 + fh * 0.74),
                int(x1 - fw * 0.08),
                int(y0 + fh * 0.90),
            )
            base = draw_atmospheric_zone(base, lower_rect, top_color, intensity=0.20, blur_scale=0.24)

    base.convert("RGB").save(out_path, quality=95)


def copy_style_reference(export_dir: Path):
    candidates = [
        REFERENCES_DIR / "style_reference_target.png",
        REFERENCES_DIR / "style_reference_target.jpg",
        REFERENCES_DIR / "style_reference_target.jpeg",
        BASE_DIR / "style_reference_target.png",
        BASE_DIR / "style_reference_target.jpg",
        BASE_DIR / "style_reference_target.jpeg",
    ]

    for style_ref in candidates:
        if style_ref.exists():
            dst = export_dir / "03_style_reference_target.png"
            safe_copy_image(style_ref, dst)
            return dst, f"Использован эталон качества: {style_ref.name}"

    note = export_dir / "03_STYLE_REFERENCE_NOT_FOUND.txt"
    note.write_text(
        "Эталон качества не найден.\n"
        "Это необязательный файл, но с ним AI обычно делает результат лучше.\n"
        "Можно положить картинку сюда: references/style_reference_target.png\n",
        encoding="utf-8",
    )
    return None, "Эталон качества не найден"


# ---------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------

def load_user_prompt():
    if PROMPT_PATH.exists():
        text = PROMPT_PATH.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            return text

    return (
        "Сделай теплую архитектурную подсветку 3000К.\n"
        "По верхнему карнизу сделай контурное освещение.\n"
        "По вертикальным членениям фасада поставь узкие вертикальные лучи снизу вверх.\n"
        "Входную группу выдели мягкой заливкой."
    )



def build_special_prompt_notes(user_prompt: str) -> str:
    low = (user_prompt or "").lower()
    facade_mode = load_facade_mode()
    notes = [
        "Подсветку распространить на всё здание в кадре слева направо, включая боковые секции и крылья.",
    ]

    if facade_mode == "modern_glass":
        notes.append("Современный стеклянный фасад: вести свет по стойкам, витражам, поясам и ребрам.")
    elif facade_mode == "classic":
        notes.append("Классический фасад: подчеркивать карнизы, пилястры, простенки и арки.")

    if is_russian_flag_task(user_prompt):
        notes.append("Триколор должен выглядеть как архитектурная подсветка, не как раскраска фасада.")

    return "\\n".join(f"- {n}" for n in notes)


def is_russian_flag_task(user_prompt: str) -> bool:
    """
    RGBW сам по себе НЕ означает флаг России.
    Флаг включаем только если явно написано: флаг / триколор / белый+синий+красный.
    """
    low = (user_prompt or "").lower()
    return (
        "флаг" in low
        or "триколор" in low
        or ("бел" in low and "син" in low and "крас" in low)
    )


def is_rgbw_task(user_prompt: str) -> bool:
    low = (user_prompt or "").lower()
    return "rgb" in low or "rgbw" in low


def detect_user_cct(user_prompt: str) -> str:
    low = (user_prompt or "").lower()

    if is_russian_flag_task(user_prompt) or is_rgbw_task(user_prompt):
        return "RGBW / цвета по заданию"

    if "5000" in low:
        return "5000К"
    if "4000" in low:
        return "4000К"
    if "3000" in low:
        return "3000К"
    if "2700" in low:
        return "2700К"
    return "по заданию пользователя"




def build_no_ies_visual_block(user_prompt: str) -> str:
    user_cct = detect_user_cct(user_prompt)
    return f"""ВИЗУАЛЬНАЯ КОНЦЕПЦИЯ БЕЗ IES:
IES-файлы не загружены, поэтому работай в режиме предварительной визуальной концепции.
Не указывай точные модели светильников, мощности, световые потоки и конкретные артикулы.
Используй только типовые световые приемы:
- линейная подсветка;
- заливающая подсветка;
- акцентные прожекторы;
- вертикальные лучи;
- мягкая подсветка входной группы / нижнего яруса.

Цветовая температура по заданию пользователя: {user_cct}.
Финальный подбор оборудования, мощности, световой поток, КСС и расчет выполняет светодизайнер после согласования концепции."""



def build_enhanced_task(raw_text: str) -> str:
    raw = (raw_text or "").replace("\\n", "\n").strip()
    if not raw:
        raw = (
            "Сделай теплую архитектурную подсветку 3000К.\n"
            "По верхнему карнизу сделай контурное освещение.\n"
            "По вертикальным членениям фасада поставь узкие вертикальные лучи снизу вверх.\n"
            "Входную группу выдели мягкой заливкой."
        )

    low = raw.lower()

    if is_russian_flag_task(raw):
        return (
            "Линейная RGBW-подсветка в логике флага России: "
            "верхние ряды — белым, средние — синим, нижние — красным. "
            "Цвета должны идти по архитектурным линиям и членениям фасада, без плоской раскраски. "
            f"Исходное описание: {raw}"
        )

    if is_rgbw_task(raw):
        return (
            "RGBW-подсветка фасада по исходному описанию пользователя. "
            "Цвета, зоны и сценарии брать из задания пользователя. "
            "Если конкретные цвета не указаны — сделать аккуратную презентационную RGBW-концепцию с мягкими архитектурными акцентами. "
            f"Исходное описание: {raw}"
        )

    temperature = ""
    if "4000" in low:
        temperature = "4000К"
    elif "5000" in low:
        temperature = "5000К"
    elif "3000" in low:
        temperature = "3000К"
    elif "2700" in low:
        temperature = "2700К"

    decisions = []
    if any(w in low for w in ["карниз", "контур", "линия", "линейн", "верх"]):
        decisions.append("линейная/контурная подсветка по верхним горизонталям, карнизам или ребрам")
    if "верх-вниз" in low or "вверх-вниз" in low or "двой" in low:
        decisions.append("двусторонние светильники верх-вниз по выраженным стойкам")
    if any(w in low for w in ["пилястр", "колон", "простен", "луч", "прожектор", "серед"]):
        decisions.append("акцентные вертикальные лучи по фасадным членениям")
    elif "вертик" in low and not any(n in low for n in ("без вертик", "не вертик", "без линий вертик", "без вертикал")):
        decisions.append("акцентные вертикальные лучи по фасадным членениям")
    if any(w in low for w in ["вход", "ар", "портал", "двер", "низ", "снизу", "цоколь"]):
        decisions.append("мягкая подсветка входа, нижнего яруса или цоколя")
    if "кирпич" in low and ("балкон" in low or "балко" in low):
        decisions.append("линейная подсветка вверх на границе кирпича под балконами")
    if any(w in low for w in ["стекл", "витраж", "панорам", "офис", "современ"]):
        decisions.append("деликатные световые пояса и акценты по стойкам/витражам")

    if not decisions:
        decisions.append("аккуратная архитектурная подсветка по геометрии фасада")

    temp_line = f" Цвет: {temperature}." if temperature else ""

    return (
        "Реалистичный ночной рендер архитектурной подсветки фасада для презентации заказчику."
        f"{temp_line} "
        "Свет: " + "; ".join(decisions) + ". "
        "Сохранить геометрию здания 1:1; не добавлять пилястры/колонны, которых нет на фото; "
        "сохранить знаки и таблички с исходного кадра. "
        f"Исходное описание: {raw}"
    )


def compact_user_task(user_prompt: str) -> str:
    """
    Для image AI оставляем только смысл задания.
    Если в поле попало старое длинное ТЗ, вытаскиваем исходное описание пользователя.
    """
    text = (user_prompt or "").replace("\\\\n", "\\n").strip()
    if not text:
        return "Сделай реалистичную ночную концепцию архитектурной подсветки фасада."

    markers = [
        "Исходное описание пользователя:",
        "исходное описание пользователя:",
        "ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ:",
        "Задание пользователя:",
    ]
    for marker in markers:
        if marker in text:
            text = text.split(marker, 1)[1].strip()
            break

    # Убираем старые служебные заголовки, если они остались.
    remove_markers = [
        "Техническая логика по IES:",
        "Требования к результату:",
        "КРИТИЧЕСКИ ВАЖНО:",
        "ИТОГ:",
        "ОГРАНИЧЕНИЯ ПО IES",
    ]
    for marker in remove_markers:
        if marker in text:
            text = text.split(marker, 1)[0].strip()

    low = text.lower()
    is_flag = is_russian_flag_task(text)

    if is_flag:
        return (
            "Линейная RGBW-подсветка в логике флага России: "
            "верхние ряды белым, средние синим, нижние красным. "
            "Цвета должны идти по архитектурным линиям и членениям фасада, без плоской раскраски."
        )

    # Обычный случай (включая RGBW): передаём задание пользователя дословно.
    one_line = " ".join(line.strip(" -") for line in text.splitlines() if line.strip())
    if len(one_line) > 500:
        one_line = one_line[:500].rstrip() + "..."
    return one_line




def summarize_ies_kss_for_prompt(ies_infos) -> str:
    """
    Короткая строка для prompt: чтобы AI видел, что IES реально учтены,
    но без огромной технической простыни.
    """
    ies_infos = ies_infos or []
    if not ies_infos:
        return "IES не загружены."

    parts = []
    for info in ies_infos:
        lum = f"{info.lumens:g} лм" if info.lumens is not None else "поток из IES"
        pwr = f"{info.power:g} Вт" if info.power is not None else "мощность из IES"
        label = info.lumcat or info.stem
        parts.append(f"{label} ({info.kind}; {lum}; {pwr})")

    return f"Загружено IES: {len(ies_infos)}. " + "; ".join(parts) + "."


def build_ies_ai_prompt_block(ies_infos) -> str:
    """Детальный блок для промпта: фотометрия и визуальные правила по каждому IES."""
    ies_infos = ies_infos or []
    if not ies_infos:
        return (
            "IES / ФОТОМЕТРИЯ: файлы не загружены — работать только по сценарию и style ref.\n"
        )

    lines = [
        "IES / ФОТОМЕТРИЯ (обязательно — источник типа света и характера пятна):",
        "Light plan и style ref не могут подменять IES. Если конфликт — приоритет у IES + сценария.",
        "",
    ]
    for i, info in enumerate(ies_infos, start=1):
        lum = f"{info.lumens:g} лм" if info.lumens is not None else "не определено"
        pwr = f"{info.power:g} Вт" if info.power is not None else "не определено"
        lines.extend([
            f"{i}) Файл: {info.file_name}",
            f"   Модель (IES): {info.lumcat or info.stem}",
            f"   КСС / тип: {info.kind}",
            f"   Поток: {lum}, мощность: {pwr}",
            f"   Характер пятна: {info.beam_hint}",
            f"   Монтаж: {info.mount_hint}",
            f"   Запрещено для этой IES: {info.forbid_hint}",
            "",
        ])
    lines.append(
        "Корпус светильника — строго как на product front. "
        "Световое пятно — строго по IES выше (форма луча, ширина, направление)."
    )
    return "\n".join(lines)


def build_compact_ies_constraints(ies_infos, user_prompt: str) -> str:
    caps = analyze_ies_capabilities(ies_infos or [])
    cct = detect_user_cct(user_prompt)
    detail = build_ies_ai_prompt_block(ies_infos or [])
    kss = summarize_ies_kss_for_prompt(ies_infos or [])

    if not caps.get("has_ies"):
        return (
            f"{detail}\n\n"
            f"{kss} Режим: визуальная концепция без привязки к IES. Цвет: {cct}."
        )

    mode_rules = ""
    if caps.get("mode") == "ground_pole":
        mode_rules = (
            "Режим IES: парковый столб NT-STEP. "
            "Свет только от наземных столбов на тротуаре, мягкие пятна на дороге. "
            "Не рисовать LED-линии на фасаде."
        )
    elif caps.get("mode") == "line_only":
        mode_rules = (
            "Режим IES: только линейная/контурная фотометрия. "
            "Рисовать непрерывные линии света, не прожекторные конусы и не заливку."
        )
    elif caps.get("mode") == "accent_only":
        mode_rules = (
            "Режим IES: акцентная/лучевая фотометрия. "
            "Направленные лучи по стойкам/ребрам, без длинных контурных полос."
        )
    elif caps.get("mode") == "wide_only":
        mode_rules = (
            "Режим IES: широкая/заливающая фотометрия. "
            "Мягкая заливка плоскостей, без тонких LED-линий."
        )
    else:
        mode_rules = "Режим IES: смешанный набор — использовать только типы света из загруженных IES."

    return (
        f"{detail}\n\n"
        f"{kss}\n"
        f"{mode_rules} Цвет: {cct}."
    )


def build_style_instruction(has_style_ref: bool) -> str:
    if has_style_ref:
        return "Style ref — только качество: реализм, ночь, контраст, мягкий объемный свет. Архитектуру не копировать."
    return "Без style ref: делать профессиональный реалистичный ночной lighting render."


def build_chatgpt_prompt(user_prompt, ies_summary, has_style_ref: bool, has_ies: bool = True, ies_infos=None):
    task = compact_user_task(user_prompt)
    ies_rules = build_compact_ies_constraints(ies_infos or [], user_prompt)
    style = build_style_instruction(has_style_ref)
    notes = build_special_prompt_notes(user_prompt)

    style_line = "3) style reference." if has_style_ref else "3) style reference может отсутствовать."
    extra = f"\\nУточнения:\\n{notes}" if notes else ""

    return f"""AI-визуализатор архитектурной подсветки.

Изображения:
1) исходное дневное фото фасада;
2) light plan reference — только смысловая карта, не копировать буквально;
{style_line}

Сделай одну реалистичную ночную визуализацию подсветки по исходному фото.

Style: {style}

Задание: {task}

IES / КСС: {ies_rules}{extra}

Правила:
- сохранить геометрию здания, этажность, окна, двери, стекло, фасадные панели и материалы;
- тип света и форма пятна — строго по блоку IES / КСС выше; light plan — только подсказка зон;
- подсветку применить ко всему зданию в кадре слева направо, без пропуска боковых секций;
- не добавлять людей, машины, вывески, логотипы, новые окна и лишние объекты;
- затемнить сцену естественно, свет должен мягко ложиться на фасад;
- не переносить в финал линии, точки, рамки, подписи и маркеры из light plan;
- не делать схему, мультяшность, грубый Photoshop или плоские цветные полосы.

Итог: одна финальная презентационная картинка без текста и интерфейса."""


def build_gemini_prompt(user_prompt, ies_summary, has_style_ref: bool, has_ies: bool = True, ies_infos=None):
    task = compact_user_task(user_prompt)
    ies_rules = build_compact_ies_constraints(ies_infos or [], user_prompt)
    style = build_style_instruction(has_style_ref)
    notes = build_special_prompt_notes(user_prompt)
    extra = f"\\nУточнения:\\n{notes}" if notes else ""

    return f"""Create one realistic night architectural lighting render from the source facade photo.

Images:
1) source daytime facade photo;
2) light plan reference — semantic guide only, do not copy literally;
3) style reference, if provided.

Style: {style}

Task: {task}

IES / КСС: {ies_rules}{extra}

Rules:
- preserve exact building geometry, floors, windows, doors, glass, facade panels and materials;
- apply lighting to the entire building in frame from left to right, including side wings;
- do not add people, cars, signs, logos, extra windows or new objects;
- darken the scene naturally;
- light must look soft, realistic and physically plausible;
- do not copy technical lines, dots, labels or frames from the light plan;
- no cartoon style, rough Photoshop, flat stripes or technical scheme look.

Final output: one presentation-quality render, no text and no UI."""


def build_how_to_use(has_style_ref: bool):
    return """КАК ПОЛЬЗОВАТЬСЯ ПАКЕТОМ

В ChatGPT / Gemini загружать только картинки:
1. 01_source_building.png — исходное фото здания.
2. 02_light_plan_reference.png — черновая карта световых зон, не точная разметка фасада.
3. 03_style_reference_target.png — эталон качества, если есть.

Файлы 04_prompt_for_chatgpt.txt, 07_ies_summary.txt, 08_equipment_draft.md загружать в AI не нужно.
Prompt уже скопирован в буфер обмена. В AI-чате нажмите Ctrl+V.

После генерации:
1. Скачайте финальную картинку.
2. В программе нажмите «Импорт рендера».
"""


def write_url_shortcut(path: Path, url: str):
    path.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")


def copy_to_clipboard(text: str):
    try:
        subprocess.run(
            "clip",
            input=text,
            text=True,
            encoding="utf-16le",
            shell=True,
            check=False,
        )
        return True
    except Exception:
        return False



def create_upload_to_ai_folder(export_dir: Path, has_style_ref: bool):
    """
    Отдельная папка только с теми файлами, которые нужно перетащить в ChatGPT/Gemini.
    Здесь не лежат prompt, ведомость и служебные txt/md, чтобы пользователь не перепутал.
    """
    upload_dir = export_dir / "SEND_TO_AI"
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    files = [
        "01_source_building.png",
        "02_light_plan_reference.png",
    ]

    if has_style_ref:
        files.append("03_style_reference_target.png")

    for name in files:
        src = export_dir / name
        if src.exists():
            shutil.copy2(src, upload_dir / name)

    readme = upload_dir / "README_что_загружать.txt"
    readme.write_text(
        "ЭТУ ПАПКУ МОЖНО ЦЕЛИКОМ ПЕРЕТАЩИТЬ В CHATGPT / GEMINI.\\n\\n"
        "Внутри только картинки, которые нужно загрузить в AI:\\n"
        "1) 01_source_building.png — исходное фото здания\\n"
        "2) 02_light_plan_reference.png — черновая карта подсветки\\n"
        "3) 03_style_reference_target.png — эталон качества, если есть\\n\\n"
        "Prompt НЕ лежит в этой папке как обязательный файл.\\n"
        "Он уже скопирован программой в буфер обмена. В AI-чате нажмите Ctrl+V.\\n",
        encoding="utf-8",
    )

    return upload_dir



# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    source_path = find_source_image()
    user_prompt = load_user_prompt()
    ies_infos = load_ies_infos()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = EXPORT_ROOT / f"facade_ai_pack_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    # 01 source
    source_dst = export_dir / "01_source_building.png"
    safe_copy_image(source_path, source_dst)

    # 02 light plan — всегда генерируем заново по текущему фото.
    light_dst = export_dir / "02_light_plan_reference.png"
    generate_light_plan_reference(source_path, light_dst, user_prompt, ies_infos=ies_infos)

    # Также сохраняем последний reference для просмотра/отладки.
    latest_light = OUTPUT_DIR / "latest_light_plan_reference.png"
    safe_copy_image(light_dst, latest_light)

    # 03 style
    style_dst, style_note = copy_style_reference(export_dir)
    has_style_ref = style_dst is not None

    # texts
    has_ies = len(ies_infos) > 0
    ies_summary = build_ies_summary(ies_infos)
    equipment = build_equipment_draft(ies_infos)

    chatgpt_prompt = build_chatgpt_prompt(user_prompt, ies_summary, has_style_ref, has_ies=has_ies, ies_infos=ies_infos)
    gemini_prompt = build_gemini_prompt(user_prompt, ies_summary, has_style_ref, has_ies=has_ies, ies_infos=ies_infos)

    (export_dir / "04_prompt_for_chatgpt.txt").write_text(chatgpt_prompt, encoding="utf-8")
    (export_dir / "05_prompt_for_gemini_nano_banana.txt").write_text(gemini_prompt, encoding="utf-8")
    (export_dir / "07_ies_summary.txt").write_text(ies_summary, encoding="utf-8")
    (export_dir / "08_equipment_draft.md").write_text(equipment, encoding="utf-8")
    (export_dir / "09_how_to_use.txt").write_text(build_how_to_use(has_style_ref), encoding="utf-8")

    write_url_shortcut(export_dir / "OPEN_ChatGPT.url", "https://chatgpt.com/")
    write_url_shortcut(export_dir / "OPEN_Gemini_Nano_Banana.url", "https://gemini.google.com/")
    write_url_shortcut(export_dir / "OPEN_Claude.url", "https://claude.ai/")

    upload_dir = create_upload_to_ai_folder(export_dir, has_style_ref)

    latest = EXPORT_ROOT / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(export_dir, latest)

    copied = copy_to_clipboard(chatgpt_prompt)

    print("")
    print("NITEOS Facade Concept — AI Packager v2.9")
    print("--------------------------------------------------")
    print(f"Исходное фото:       {source_dst}")
    print(f"Черновая карта:      {light_dst}")
    print(f"Эталон качества:     {style_note}")
    print(f"IES файлов:          {len(ies_infos)}" if ies_infos else "IES файлов:          нет — визуальный режим")
    print(f"Режим IES карты:     {analyze_ies_capabilities(ies_infos).get('summary')}")
    print(f"Папка latest:        {latest}")
    print(f"Загрузить в AI:      {latest / 'SEND_TO_AI'}")
    print("Prompt скопирован в буфер." if copied else "Prompt не удалось скопировать автоматически.")
    print("")


if __name__ == "__main__":
    main()
