from pathlib import Path
import base64
import json
import mimetypes
import os
import sys
import io
import contextlib
import importlib
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont


APP_TITLE = "НИТЕОС Концепт света v1.3.9"


def app_base_dir() -> Path:
    """
    В обычном запуске база — папка .py файла.
    В собранном .exe база — папка рядом с exe.
    Так пользователь может переносить всю папку программы на другой компьютер.
    """
    override = os.environ.get("NITEOS_BASE_DIR", "").strip()
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_base_dir()


def bundled_assets_dir() -> Path:
    """
    Рабочие папки создаем рядом с exe, но assets в PyInstaller one-folder
    обычно лежат в _internal/assets. Поэтому ищем логотипы отдельно.
    """
    candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "assets",
            exe_dir / "_internal" / "assets",
        ])

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets")

    candidates.append(Path(__file__).resolve().parent / "assets")
    candidates.append(BASE_DIR / "assets")

    for p in candidates:
        if (p / "niteos_logo.png").exists() or (p / "niteos_logo_splash.png").exists():
            return p

    # fallback: пусть будет папка рядом с программой
    return BASE_DIR / "assets"


RESOURCE_ASSETS_DIR = bundled_assets_dir()
USER_ASSETS_DIR = BASE_DIR / "assets"

INPUT_DIR = BASE_DIR / "input"
IES_DIR = BASE_DIR / "ies_library"
REFERENCES_DIR = BASE_DIR / "references"
OUTPUT_DIR = BASE_DIR / "output"
EXPORT_DIR = BASE_DIR / "project_export"
ASSETS_DIR = USER_ASSETS_DIR
EXAMPLES_DIR = BASE_DIR / "examples"
SOURCE_EXAMPLES_DIR = EXAMPLES_DIR / "source_photos"
IES_EXAMPLES_DIR = EXAMPLES_DIR / "ies"
STYLE_EXAMPLES_DIR = EXAMPLES_DIR / "style_references"

PROMPT_PATH = BASE_DIR / "prompt.txt"
MODE_PATH = BASE_DIR / "facade_mode.txt"
API_KEY_PATH = BASE_DIR / "gemini_api_key.txt"
GEMINI_MODEL_PATH = BASE_DIR / "gemini_model.txt"
ROUTERAI_API_KEY_PATH = BASE_DIR / "routerai_api_key.txt"
ROUTERAI_MODEL_PATH = BASE_DIR / "routerai_model.txt"
API_PROVIDER_PATH = BASE_DIR / "api_provider.txt"
LOGO_PATH = RESOURCE_ASSETS_DIR / "niteos_logo.png"
SPLASH_LOGO_PATH = RESOURCE_ASSETS_DIR / "niteos_logo_splash.png"
STYLE_PATH = REFERENCES_DIR / "style_reference_target.png"
SOURCE_PATH = INPUT_DIR / "building.png"
FINAL_PATH = OUTPUT_DIR / "final_imported_render.png"
API_FINAL_PATH = OUTPUT_DIR / "gemini_generated_render.png"
API_EDITED_PATH = OUTPUT_DIR / "gemini_edited_render.png"

for p in [INPUT_DIR, IES_DIR, REFERENCES_DIR, OUTPUT_DIR, EXPORT_DIR, ASSETS_DIR, SOURCE_EXAMPLES_DIR, IES_EXAMPLES_DIR, STYLE_EXAMPLES_DIR]:
    p.mkdir(exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


COLORS = {
    "bg": "#030405",
    "bg2": "#070809",
    "card": "#0A0C0F",
    "card2": "#101318",
    "input": "#050609",
    "border": "#3B424A",
    "border2": "#565F6A",
    "accent": "#D7DEE8",
    "accent2": "#AAB4C1",
    "accent_dark": "#1C222A",
    "text": "#F1F4F7",
    "muted": "#8D97A3",
    "soft": "#B8C1CC",
    "green": "#B7F7D3",
    "gold": "#D8B978",
    "red": "#D78484",
}


DEFAULT_PROMPT = (
    "Сделай теплую архитектурную подсветку 3000К.\n"
    "По верхнему карнизу сделай контурное освещение.\n"
    "По пилястрам поставь узкие вертикальные лучи снизу вверх.\n"
    "Центральный вход выдели мягкой заливкой."
)


def open_folder(path: Path):
    path.mkdir(exist_ok=True)
    try:
        os.startfile(str(path))
    except Exception:
        webbrowser.open(path.as_uri())


def copy_text_to_clipboard(text: str):
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


def save_rgb(src: Path, dst: Path):
    img = Image.open(src).convert("RGB")
    img.save(dst, quality=95)


def read_secret_file(path: Path):
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            return text
    except Exception:
        pass
    return ""


def get_gemini_api_key():
    return (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
        or read_secret_file(API_KEY_PATH)
    )


def get_gemini_model():
    return (
        os.environ.get("GEMINI_IMAGE_MODEL", "").strip()
        or read_secret_file(GEMINI_MODEL_PATH)
        or "gemini-2.5-flash-image-preview"
    )


def get_routerai_api_key():
    return (
        os.environ.get("ROUTERAI_API_KEY", "").strip()
        or read_secret_file(ROUTERAI_API_KEY_PATH)
    )


def get_routerai_model():
    return (
        os.environ.get("ROUTERAI_IMAGE_MODEL", "").strip()
        or read_secret_file(ROUTERAI_MODEL_PATH)
        or "google/gemini-2.5-flash-image"
    )


def get_api_provider():
    value = (os.environ.get("NITEOS_API_PROVIDER", "").strip() or read_secret_file(API_PROVIDER_PATH) or "routerai").lower()
    if value not in {"routerai", "gemini"}:
        return "routerai"
    return value


def save_api_provider(provider: str):
    provider = (provider or "routerai").strip().lower()
    if provider in {"routerai", "gemini"}:
        API_PROVIDER_PATH.write_text(provider, encoding="utf-8")


def save_gemini_settings(api_key: str, model: str):
    api_key = (api_key or "").strip()
    model = (model or "").strip()
    if api_key:
        API_KEY_PATH.write_text(api_key, encoding="utf-8")
    if model:
        GEMINI_MODEL_PATH.write_text(model, encoding="utf-8")


def save_routerai_settings(api_key: str, model: str):
    api_key = (api_key or "").strip()
    model = (model or "").strip()
    if api_key:
        ROUTERAI_API_KEY_PATH.write_text(api_key, encoding="utf-8")
    if model:
        ROUTERAI_MODEL_PATH.write_text(model, encoding="utf-8")


def image_inline_part(path: Path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"inline_data": {"mime_type": mime, "data": data}}


def image_data_url(path: Path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def find_base64_images(obj):
    found = []
    if isinstance(obj, dict):
        inline = obj.get("inlineData") or obj.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            found.append((inline.get("mimeType") or inline.get("mime_type") or "image/png", inline.get("data")))
        for value in obj.values():
            found.extend(find_base64_images(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_base64_images(item))
    return found


def save_first_response_image(response_json, out_path: Path):
    images = find_base64_images(response_json)
    if not images:
        raise RuntimeError("Gemini did not return an image. Check model name and prompt.")

    mime, data = images[0]
    raw = base64.b64decode(data)
    tmp_path = out_path.with_suffix(".api_tmp")
    tmp_path.write_bytes(raw)
    try:
        save_rgb(tmp_path, out_path)
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
    return out_path


def save_data_url_image(value: str, out_path: Path):
    if not value:
        raise RuntimeError("Image URL is empty.")
    if value.startswith("data:"):
        header, data = value.split(",", 1)
        raw = base64.b64decode(data)
    else:
        with urllib.request.urlopen(value, timeout=180) as response:
            raw = response.read()

    tmp_path = out_path.with_suffix(".api_tmp")
    tmp_path.write_bytes(raw)
    try:
        save_rgb(tmp_path, out_path)
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
    return out_path


def save_first_openai_response_image(response_json, out_path: Path):
    choices = response_json.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        images = message.get("images") or []
        for image in images:
            image_url = image.get("image_url") or {}
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if url:
                return save_data_url_image(url, out_path)

        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                image_url = part.get("image_url") or part.get("image")
                if isinstance(image_url, dict) and image_url.get("url"):
                    return save_data_url_image(image_url.get("url"), out_path)
                if isinstance(image_url, str):
                    return save_data_url_image(image_url, out_path)

    images = find_base64_images(response_json)
    if images:
        return save_first_response_image(response_json, out_path)

    raise RuntimeError("RouterAI did not return an image. Check model name, balance and response format.")


def call_gemini_image_api(prompt: str, image_paths, out_path: Path, api_key: str = "", model: str = ""):
    api_key = (api_key or get_gemini_api_key()).strip()
    model = (model or get_gemini_model()).strip()
    if not api_key:
        raise RuntimeError("Gemini API key is missing.")
    if not model:
        raise RuntimeError("Gemini model is missing.")

    parts = [{"text": prompt.strip()}]
    for path in image_paths:
        if path and Path(path).exists():
            parts.append(image_inline_part(Path(path)))

    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    payload = json.dumps(body).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini API error {e.code}: {details[:1200]}") from e

    return save_first_response_image(response_json, out_path)


def call_routerai_image_api(prompt: str, image_paths, out_path: Path, api_key: str = "", model: str = ""):
    api_key = (api_key or get_routerai_api_key()).strip()
    model = (model or get_routerai_model()).strip()
    if not api_key:
        raise RuntimeError("RouterAI API key is missing.")
    if not model:
        raise RuntimeError("RouterAI model is missing.")

    content = [{"type": "text", "text": prompt.strip()}]
    for path in image_paths:
        if path and Path(path).exists():
            content.append({"type": "image_url", "image_url": {"url": image_data_url(Path(path))}})

    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["text", "image"],
        "image_config": {
            "aspect_ratio": "16:9",
            "image_size": "2K",
        },
    }
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        "https://routerai.ru/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"RouterAI API error {e.code}: {details[:1200]}") from e

    return save_first_openai_response_image(response_json, out_path)


def call_selected_image_api(provider: str, prompt: str, image_paths, out_path: Path, gemini_key: str = "", gemini_model: str = "", routerai_key: str = "", routerai_model: str = ""):
    provider = (provider or "routerai").strip().lower()
    if provider == "gemini":
        return call_gemini_image_api(prompt, image_paths, out_path, gemini_key, gemini_model)
    return call_routerai_image_api(prompt, image_paths, out_path, routerai_key, routerai_model)


def ies_files_in(folder: Path, recursive: bool = False):
    """
    Возвращает .ies файлы без зависимости от регистра расширения.
    Если recursive=True, ищет также во вложенных папках.
    """
    folder = Path(folder)
    if not folder.exists():
        return []

    iterator = folder.rglob("*") if recursive else folder.iterdir()
    files = []
    for p in iterator:
        try:
            if p.is_file() and p.suffix.lower() == ".ies":
                files.append(p)
        except Exception:
            pass

    # Убираем возможные дубли по полному пути.
    unique = []
    seen = set()
    for p in files:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return sorted(unique, key=lambda x: x.name.lower())


def image_files_in(folder: Path, recursive: bool = False):
    folder = Path(folder)
    if not folder.exists():
        return []

    iterator = folder.rglob("*") if recursive else folder.iterdir()
    files = []
    for p in iterator:
        try:
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                files.append(p)
        except Exception:
            pass

    unique = []
    seen = set()
    for p in files:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return sorted(unique, key=lambda x: x.name.lower())


def unique_display_paths(paths):
    result = {}
    used = set()
    for path in paths:
        label = path.name
        if label.lower() in used:
            label = f"{path.parent.name}/{path.name}"
        used.add(label.lower())
        result[label] = path
    return result


def count_ies():
    return len(ies_files_in(IES_DIR, recursive=False))


def make_fit_ctk_image(path: Path, box_w: int, box_h: int, bg="#030405"):
    src = Image.open(path).convert("RGB")
    src.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (box_w, box_h), bg)
    x = (box_w - src.width) // 2
    y = (box_h - src.height) // 2
    canvas.paste(src, (x, y))
    return ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(box_w, box_h))


def make_preview_ctk_image(path: Path, size):
    img = Image.open(path).convert("RGB")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)


def make_noir_placeholder(width=780, height=520):
    """
    Абстрактный noir/futuristic placeholder без сторонних картинок.
    Не используется как style-reference, только как пустой экран preview.
    """
    img = Image.new("RGB", (width, height), "#030405")
    d = ImageDraw.Draw(img)

    # мягкий вертикальный градиент
    for y in range(height):
        t = y / max(1, height)
        v = int(5 + 22 * t)
        d.line([(0, y), (width, y)], fill=(v, v, v + 2))

    # тонкая сетка
    for x in range(0, width, 42):
        d.line([(x, 0), (x, height)], fill="#111419")
    for y in range(0, height, 42):
        d.line([(0, y), (width, y)], fill="#111419")

    # абстрактные перспективные линии
    cx, cy = width // 2, int(height * 0.62)
    for i in range(-9, 10):
        x = int(width * 0.5 + i * width * 0.055)
        d.line([(cx, cy), (x, height)], fill="#222832", width=1)
    for i in range(8):
        y = int(height * 0.35 + i * height * 0.065)
        d.line([(int(width * 0.18), y), (int(width * 0.82), y)], fill="#171B21", width=1)

    # геометрические темные силуэты
    shapes = [
        [(80, 430), (150, 220), (205, 430)],
        [(210, 430), (280, 145), (330, 430)],
        [(500, 430), (560, 170), (620, 430)],
        [(620, 430), (685, 230), (735, 430)],
    ]
    for pts in shapes:
        d.polygon(pts, fill="#080A0D", outline="#303640")

    # световая линия
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line([(int(width*0.18), int(height*0.76)), (int(width*0.82), int(height*0.76))], fill=(220, 225, 235, 115), width=2)
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    d = ImageDraw.Draw(img)
    d.text((36, 36), "NITEOS FACADE CONCEPT", fill="#F1F4F7")
    d.text((36, 66), "NOIR AI LIGHTING WORKSPACE", fill="#8D97A3")
    d.text((36, height - 44), "Загрузите фото фасада или импортируйте финальный AI-рендер", fill="#6F7884")

    return img


def load_ui_font(size=18, bold=False):
    # Windows обычно находит эти имена сам. Если нет — используем стандартный шрифт PIL.
    candidates = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def draw_centered_text(draw, xy, text, font, fill, anchor="mm"):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def make_splash_bg(width=580, height=360):
    """
    Чистая заставка без грубых черных плашек:
    - темный градиент;
    - тонкая сетка;
    - мягкое синее свечение;
    - аккуратная двойная рамка;
    - весь текст рисуется прямо на фоне, поэтому не появляется топорных прямоугольников.
    """
    scale = 2
    W, H = width * scale, height * scale

    base = Image.new("RGBA", (W, H), (3, 4, 6, 255))
    d = ImageDraw.Draw(base)

    # Вертикальный градиент
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(4 + 8 * (1 - t))
        g = int(5 + 12 * (1 - t))
        b = int(8 + 24 * (1 - t))
        d.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Мягкое центральное холодное свечение
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        [int(W * 0.18), int(H * 0.02), int(W * 0.82), int(H * 0.78)],
        fill=(40, 85, 140, 38),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(70 * scale))
    base = Image.alpha_composite(base, glow)

    d = ImageDraw.Draw(base)

    # Сетка
    grid_color = (90, 105, 125, 24)
    for x in range(0, W, 44 * scale):
        d.line([(x, 0), (x, H)], fill=grid_color, width=1)
    for y in range(0, H, 32 * scale):
        d.line([(0, y), (W, y)], fill=grid_color, width=1)

    # Перспективные линии внизу
    vanishing = (W // 2, int(H * 0.58))
    for x in range(-W, W * 2, 70 * scale):
        d.line([(x, H), vanishing], fill=(80, 95, 125, 26), width=1)
    for i in range(8):
        y = int(H * (0.78 + i * 0.028))
        d.line([(int(W*0.12), y), (int(W*0.88), y)], fill=(80, 95, 125, 22), width=1)

    # Аккуратная рамка
    for i, alpha in enumerate([145, 80]):
        pad = (18 + i * 7) * scale
        d.rounded_rectangle(
            [pad, pad, W - pad, H - pad],
            radius=26 * scale,
            outline=(210, 220, 235, alpha),
            width=1 * scale,
        )

    # Логотип
    logo_path = SPLASH_LOGO_PATH if SPLASH_LOGO_PATH.exists() else LOGO_PATH
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        max_w, max_h = int(W * 0.48), int(H * 0.24)
        k = min(max_w / logo.width, max_h / logo.height, 1.0)
        logo = logo.resize((max(1, int(logo.width * k)), max(1, int(logo.height * k))), Image.Resampling.LANCZOS)

        # Слабая тень под логотипом
        shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        shadow_arr = logo.split()[-1].filter(ImageFilter.GaussianBlur(7 * scale))
        shadow.putalpha(shadow_arr)
        shadow = Image.new("RGBA", logo.size, (0, 0, 0, 110))
        shadow.putalpha(shadow_arr)

        lx = (W - logo.width) // 2
        ly = int(H * 0.105)
        base.alpha_composite(shadow, (lx + 2 * scale, ly + 3 * scale))
        base.alpha_composite(logo, (lx, ly))

    # Тексты
    d = ImageDraw.Draw(base)
    title_font = load_ui_font(26 * scale, bold=True)
    sub_font = load_ui_font(13 * scale, bold=True)
    small_font = load_ui_font(10 * scale, bold=False)
    author_font = load_ui_font(11 * scale, bold=True)

    # Мягкая тень для текста
    def text_shadowed(y, text, font, fill):
        d.text((W // 2 + 2 * scale, y + 2 * scale), text, font=font, fill=(0, 0, 0, 150), anchor="mm")
        d.text((W // 2, y), text, font=font, fill=fill, anchor="mm")

    text_shadowed(int(H * 0.52), "НИТЕОС КОНЦЕПТ СВЕТА", title_font, (245, 248, 252, 255))
    text_shadowed(int(H * 0.64), "AI-подготовка концепций архитектурной подсветки", sub_font, (205, 215, 228, 255))
    d.text((W // 2, int(H * 0.77)), "ChatGPT / Gemini / Nano Banana", font=small_font, fill=(150, 160, 174, 255), anchor="mm")
    d.text((W // 2, int(H * 0.875)), "by Илья Вихерев", font=author_font, fill=(205, 215, 228, 255), anchor="mm")

    base = base.resize((width, height), Image.Resampling.LANCZOS)
    return base.convert("RGB")


class Splash(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=COLORS["bg"])

        w, h = 620, 390
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        bg = make_splash_bg(w, h)
        self.bg_img = ctk.CTkImage(light_image=bg, dark_image=bg, size=(w, h))
        ctk.CTkLabel(self, text="", image=self.bg_img, fg_color=COLORS["bg"]).place(x=0, y=0, relwidth=1, relheight=1)



class AIWorkspaceDialog(ctk.CTkToplevel):
    def __init__(self, master, latest_dir: Path):
        super().__init__(master)
        self.title("AI-рабочее место")
        self.geometry("620x520")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.latest_dir = latest_dir

        self.platform_var = ctk.StringVar(value="chatgpt")

        self.platforms = {
            "chatgpt": {
                "name": "ChatGPT",
                "url": "https://chatgpt.com/",
                "note": "Лучший вариант для финального AI-рендера и работы с несколькими изображениями."
            },
            "gemini": {
                "name": "Gemini / Nano Banana",
                "url": "https://gemini.google.com/",
                "note": "Хороший вариант для быстрых визуализаций и альтернативных результатов."
            },
            "claude": {
                "name": "Claude",
                "url": "https://claude.ai/",
                "note": "Лучше использовать для улучшения текста prompt, не как основной image-render."
            },
        }

        self.transient(master)
        self.grab_set()

        frame = ctk.CTkFrame(
            self,
            corner_radius=28,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border2"],
        )
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            frame,
            text="AI-рабочее место",
            text_color=COLORS["text"],
            font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w", padx=24, pady=(22, 6))

        ctk.CTkLabel(
            frame,
            text="Программа открывает отдельную папку SEND_TO_AI только с картинками для загрузки, копирует prompt и открывает выбранную AI-платформу.",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
            wraplength=540,
            justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # Инструкция
        steps_frame = ctk.CTkFrame(
            frame,
            corner_radius=18,
            fg_color=COLORS["input"],
            border_width=1,
            border_color=COLORS["border"],
        )
        steps_frame.pack(fill="x", padx=24, pady=(0, 14))

        steps = [
            "1. Открой папку SEND_TO_AI",
            "2. Перетащи все картинки из нее в AI-чат",
            "3. Там нет служебных файлов, только то, что надо загрузить",
            "4. Prompt уже скопирован. В AI-чате нажми Ctrl+V",
            "5. Скачай результат и нажми в программе «Загрузить результат из AI»",
        ]

        for s in steps:
            ctk.CTkLabel(
                steps_frame,
                text=s,
                text_color=COLORS["soft"],
                font=("Segoe UI", 12, "bold"),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=18, pady=3)

        # Выбор платформы
        ctk.CTkLabel(
            frame,
            text="Куда отправляем?",
            text_color=COLORS["soft"],
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(2, 8))

        platform_frame = ctk.CTkFrame(frame, fg_color="transparent")
        platform_frame.pack(fill="x", padx=24, pady=(0, 10))

        self.radio_chatgpt = ctk.CTkRadioButton(
            platform_frame,
            text="ChatGPT",
            variable=self.platform_var,
            value="chatgpt",
            command=self.update_platform_note,
            text_color=COLORS["text"],
            fg_color="#D7DEE8",
            hover_color="#FFFFFF",
            border_color=COLORS["border2"],
        )
        self.radio_chatgpt.pack(anchor="w", pady=3)

        self.radio_gemini = ctk.CTkRadioButton(
            platform_frame,
            text="Gemini / Nano Banana",
            variable=self.platform_var,
            value="gemini",
            command=self.update_platform_note,
            text_color=COLORS["text"],
            fg_color="#D7DEE8",
            hover_color="#FFFFFF",
            border_color=COLORS["border2"],
        )
        self.radio_gemini.pack(anchor="w", pady=3)

        self.radio_claude = ctk.CTkRadioButton(
            platform_frame,
            text="Claude",
            variable=self.platform_var,
            value="claude",
            command=self.update_platform_note,
            text_color=COLORS["text"],
            fg_color="#D7DEE8",
            hover_color="#FFFFFF",
            border_color=COLORS["border2"],
        )
        self.radio_claude.pack(anchor="w", pady=3)

        self.note_label = ctk.CTkLabel(
            frame,
            text="",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
            wraplength=540,
            justify="left",
            anchor="w",
        )
        self.note_label.pack(fill="x", padx=24, pady=(0, 12))
        self.update_platform_note()

        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", padx=24, pady=(2, 8))

        ctk.CTkButton(
            row1,
            text="Открыть файлы для AI",
            height=42,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=lambda: open_folder(self.latest_dir / "SEND_TO_AI" if (self.latest_dir / "SEND_TO_AI").exists() else self.latest_dir),
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            row1,
            text="Скопировать prompt",
            height=42,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=self.copy_prompt,
        ).pack(side="left", expand=True, fill="x")

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", padx=24, pady=(0, 20))

        ctk.CTkButton(
            row2,
            text="Открыть выбранную платформу",
            height=44,
            corner_radius=16,
            fg_color="#D7DEE8",
            hover_color="#FFFFFF",
            text_color="#030405",
            font=("Segoe UI", 13, "bold"),
            command=self.open_selected_platform,
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            row2,
            text="Закрыть",
            height=44,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x")

    def update_platform_note(self):
        key = self.platform_var.get()
        data = self.platforms.get(key, self.platforms["chatgpt"])
        self.note_label.configure(text=data["note"])

    def open_selected_platform(self):
        key = self.platform_var.get()
        data = self.platforms.get(key, self.platforms["chatgpt"])
        open_folder(self.latest_dir / "SEND_TO_AI" if (self.latest_dir / "SEND_TO_AI").exists() else self.latest_dir)
        self.copy_prompt(show_message=False)
        webbrowser.open(data["url"])

    def copy_prompt(self, show_message=True):
        prompt_file = self.latest_dir / "04_prompt_for_chatgpt.txt"
        if not prompt_file.exists():
            if show_message:
                messagebox.showwarning("Prompt не найден", "В папке latest нет файла 04_prompt_for_chatgpt.txt.")
            return False

        text = prompt_file.read_text(encoding="utf-8", errors="ignore")
        ok = copy_text_to_clipboard(text)

        if show_message:
            if ok:
                messagebox.showinfo("Готово", "Prompt скопирован в буфер обмена.")
            else:
                messagebox.showwarning("Не получилось", "Не удалось скопировать prompt автоматически. Открой 04_prompt_for_chatgpt.txt вручную.")

        return ok


class ReadyDialog(ctk.CTkToplevel):
    def __init__(self, master, latest_dir: Path):
        super().__init__(master)
        self.title("Файлы для AI готовы")
        self.geometry("660x650")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.latest_dir = latest_dir
        self.transient(master)
        self.grab_set()

        frame = ctk.CTkFrame(
            self,
            corner_radius=28,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border2"],
        )
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            frame,
            text="Файлы для AI готовы",
            text_color=COLORS["text"],
            font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w", padx=24, pady=(24, 6))

        ctk.CTkLabel(
            frame,
            text="Картинки для загрузки лежат отдельно в папке SEND_TO_AI",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
        ).pack(anchor="w", padx=24, pady=(0, 18))

        ctk.CTkLabel(
            frame,
            text="Загружать в ChatGPT / Gemini:",
            text_color=COLORS["soft"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(2, 6))

        upload_files = [
            "✓ 01_source_building.png — исходное фото",
            "✓ 02_light_plan_reference.png — схема подсветки",
            "✓ 03_style_reference_target.png — эталон качества, если есть",
        ]

        for item in upload_files:
            ctk.CTkLabel(
                frame,
                text=item,
                text_color=COLORS["green"],
                font=("Segoe UI", 13, "bold"),
                anchor="w",
            ).pack(fill="x", padx=30, pady=3)

        ctk.CTkLabel(
            frame,
            text="Не загружать в AI как файлы:",
            text_color=COLORS["soft"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(14, 6))

        service_files = [
            "• 04_prompt_for_chatgpt.txt — текст уже скопирован, просто Ctrl+V",
            "• 07_ies_summary.txt — служебная сводка",
            "• 08_equipment_draft.md — предварительная ведомость",
        ]

        for item in service_files:
            ctk.CTkLabel(
                frame,
                text=item,
                text_color=COLORS["muted"],
                font=("Segoe UI", 12),
                anchor="w",
            ).pack(fill="x", padx=30, pady=2)

        ctk.CTkLabel(
            frame,
            text="Открой SEND_TO_AI и перетащи картинки в AI-чат. Prompt вставляется текстом через Ctrl+V.",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
            wraplength=450,
            justify="left",
        ).pack(anchor="w", padx=24, pady=(14, 10))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(12, 18))

        ctk.CTkButton(
            row,
            text="Открыть файлы для AI",
            height=42,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=lambda: open_folder(self.latest_dir / "SEND_TO_AI" if (self.latest_dir / "SEND_TO_AI").exists() else self.latest_dir),
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            row,
            text="AI-рабочее место",
            height=42,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=lambda: AIWorkspaceDialog(master, self.latest_dir),
        ).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(
            row,
            text="ОК",
            height=42,
            corner_radius=16,
            fg_color="#1C222A",
            hover_color="#2C333D",
            border_width=1,
            border_color=COLORS["border2"],
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1360x820")
        self.minsize(1180, 720)
        self.configure(fg_color=COLORS["bg"])

        self.logo_ctk = None
        self.source_preview = None
        self.style_preview = None
        self.hero_preview = None
        self.current_hero_path = None
        self.preview_mode = "source"
        self.preview_buttons = {}
        self.facade_mode_var = ctk.StringVar(value="Авто")

        self.source_example_paths = {}
        self.style_example_paths = {}
        self.api_key_var = ctk.StringVar(value=get_gemini_api_key())
        self.gemini_model_var = ctk.StringVar(value=get_gemini_model())
        self.api_provider_var = ctk.StringVar(value="RouterAI" if get_api_provider() == "routerai" else "Gemini direct")
        self.routerai_api_key_var = ctk.StringVar(value=get_routerai_api_key())
        self.routerai_model_var = ctk.StringVar(value=get_routerai_model())

        self.build_ui()
        self.load_existing()
        # Если пользователь вручную поменял файлы в папке ies_library,
        # счетчик обновится при возвращении в окно программы.
        self.bind("<FocusIn>", lambda e: (self.update_ies_count(), self.refresh_example_menus()))

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------

    def card(self, parent, title, number=None):
        frame = ctk.CTkFrame(
            parent,
            corner_radius=24,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border"],
        )

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 8))

        if number is not None:
            ctk.CTkLabel(
                head,
                text=str(number),
                width=28,
                height=28,
                corner_radius=9,
                fg_color="#D7DEE8",
                text_color="#030405",
                font=("Segoe UI", 13, "bold"),
            ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            head,
            text=title,
            text_color=COLORS["text"],
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")

        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        return frame, body

    def small_button(self, parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            height=38,
            corner_radius=15,
            fg_color="#151A20",
            hover_color="#252B33",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            font=("Segoe UI", 12, "bold"),
            command=command,
        )

    def status_chip(self, parent, text, color):
        return ctk.CTkLabel(
            parent,
            text=text,
            height=34,
            corner_radius=14,
            fg_color="#0A0C0F",
            text_color=color,
            font=("Segoe UI", 12, "bold"),
            padx=12,
        )

    def main_button(self, parent, text, command, height=46):
        return ctk.CTkButton(
            parent,
            text=text,
            height=height,
            corner_radius=17,
            fg_color="#D7DEE8",
            hover_color="#FFFFFF",
            text_color="#030405",
            font=("Segoe UI", 14, "bold"),
            command=command,
        )

    # ---------------------------------------------------------------------
    # Build UI
    # ---------------------------------------------------------------------

    def build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self.build_header()
        self.build_left()
        self.build_middle()
        self.build_right()
        self.build_footer()

    def build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=22, pady=(0, 10))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="by Илья Вихерев",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12, "bold"),
            anchor="center",
        ).grid(row=0, column=0, sticky="ew")

    def build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=22, pady=(18, 10))
        header.grid_columnconfigure(1, weight=1)

        if LOGO_PATH.exists():
            # В шапке также не уменьшаем сам файл, а задаем размер отображения.
            logo = Image.open(LOGO_PATH).convert("RGBA")
            max_w, max_h = 128, 58
            scale = min(max_w / logo.width, max_h / logo.height, 1.0)
            display_size = (max(1, int(logo.width * scale)), max(1, int(logo.height * scale)))
            self.logo_ctk = ctk.CTkImage(light_image=logo, dark_image=logo, size=display_size)
            ctk.CTkLabel(header, text="", image=self.logo_ctk, fg_color="transparent").grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16))
        else:
            ctk.CTkLabel(
                header,
                text="NITEOS",
                text_color=COLORS["text"],
                font=("Segoe UI", 24, "bold"),
            ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            title_box,
            text="НИТЕОС КОНЦЕПТ СВЕТА",
            text_color=COLORS["text"],
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="AI-подготовка концепций архитектурной подсветки",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(2, 0))

        chips = ctk.CTkFrame(header, fg_color="transparent")
        chips.grid(row=0, column=2, sticky="e")

        self.photo_chip = self.status_chip(chips, "Фото: нет", COLORS["red"])
        self.photo_chip.pack(side="left", padx=5)
        self.ies_chip = self.status_chip(chips, "IES: нет / визуальный режим", COLORS["gold"])
        self.ies_chip.pack(side="left", padx=5)
        self.style_chip = self.status_chip(chips, "Style: нет", COLORS["red"])
        self.style_chip.pack(side="left", padx=5)

    def build_left(self):
        # Левая колонка теперь прокручивается: на небольших экранах блок "Эталон качества"
        # больше не сжимается в тонкую полоску.
        left = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            width=390,
            scrollbar_button_color="#2C333D",
            scrollbar_button_hover_color="#4A535F",
        )
        left.grid(row=1, column=0, sticky="ns", padx=(22, 10), pady=(0, 18))

        card, body = self.card(left, "Исходное фото фасада", 1)
        card.pack(fill="x", pady=(0, 12))

        self.source_img_label = ctk.CTkLabel(
            body,
            text="Загрузите фото",
            width=340,
            height=205,
            corner_radius=18,
            fg_color=COLORS["input"],
            text_color=COLORS["muted"],
        )
        self.source_img_label.pack(fill="x", pady=(0, 12))

        self.source_name_label = ctk.CTkLabel(body, text="Файл не выбран", text_color=COLORS["muted"], anchor="w")
        self.source_name_label.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self.main_button(row, "Загрузить фото", self.load_source_photo, height=40).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.small_button(row, "input", lambda: open_folder(INPUT_DIR)).pack(side="left")
        row.winfo_children()[-1].configure(width=90)
        self.source_example_menu = ctk.CTkOptionMenu(
            body,
            values=["Примеры: нет файлов"],
            command=self.select_source_example,
            height=36,
            corner_radius=14,
            fg_color="#151A20",
            button_color="#252B33",
            button_hover_color="#343B45",
            dropdown_fg_color="#151A20",
            dropdown_hover_color="#252B33",
            text_color=COLORS["text"],
        )
        self.source_example_menu.pack(fill="x", pady=(10, 0))

        card, body = self.card(left, "IES-файлы светильников", 2)
        card.pack(fill="x", pady=(0, 12))

        self.ies_label = ctk.CTkLabel(body, text="IES: нет\nРежим: визуальная концепция без IES", text_color=COLORS["text"], anchor="w", font=("Segoe UI", 13, "bold"))
        self.ies_label.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            body,
            text="IES необязательны. Если они есть — программа учтет КСС, поток и мощность. Если нет — работает визуальный режим без привязки к светильникам.",
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=330,
            justify="left",
        ).pack(fill="x", pady=(0, 12))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self.main_button(row, "Загрузить папку IES", self.load_ies_folder, height=40).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.small_button(row, "Обновить", self.update_ies_count).pack(side="left", padx=(0, 8))
        row.winfo_children()[-1].configure(width=88)
        self.small_button(row, "Открыть", lambda: open_folder(IES_DIR)).pack(side="left")
        row.winfo_children()[-1].configure(width=82)
        row_examples = ctk.CTkFrame(body, fg_color="transparent")
        row_examples.pack(fill="x", pady=(10, 0))
        self.small_button(row_examples, "Загрузить IES-примеры", self.load_ies_examples).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.small_button(row_examples, "examples/ies", lambda: open_folder(IES_EXAMPLES_DIR)).pack(side="left")
        row_examples.winfo_children()[-1].configure(width=112)

        card, body = self.card(left, "Эталон качества / style reference", 3)
        card.pack(fill="x", pady=(0, 12))
        # Блок находится в прокручиваемой левой колонке, поэтому не фиксируем высоту.
        # Иначе кнопки "Заменить / удалить / увеличить" обрезаются снизу.
        card.pack_propagate(True)

        self.style_img_label = ctk.CTkLabel(
            body,
            text="Можно оставить пустым",
            width=340,
            height=175,
            corner_radius=18,
            fg_color=COLORS["input"],
            text_color=COLORS["muted"],
        )
        self.style_img_label.pack(fill="x", pady=(0, 12))

        self.style_name_label = ctk.CTkLabel(
            body,
            text="Необязательно. Можно заменить прямо из программы",
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=330,
            justify="left",
        )
        self.style_name_label.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self.main_button(row, "Заменить эталон", self.load_style_reference, height=40).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.small_button(row, "удалить", self.clear_style_reference).pack(side="left", padx=(0, 8))
        row.winfo_children()[-1].configure(width=82)
        self.small_button(row, "увеличить", self.open_style_reference).pack(side="left")
        row.winfo_children()[-1].configure(width=96)
        self.style_example_menu = ctk.CTkOptionMenu(
            body,
            values=["Примеры: нет файлов"],
            command=self.select_style_example,
            height=36,
            corner_radius=14,
            fg_color="#151A20",
            button_color="#252B33",
            button_hover_color="#343B45",
            dropdown_fg_color="#151A20",
            dropdown_hover_color="#252B33",
            text_color=COLORS["text"],
        )
        self.style_example_menu.pack(fill="x", pady=(10, 0))

    def build_middle(self):
        mid = ctk.CTkFrame(self, fg_color="transparent", width=450)
        mid.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 18))
        mid.grid_propagate(False)

        card, body = self.card(mid, "Задание на подсветку", 4)
        card.pack(fill="both", expand=True)

        self.prompt_box = ctk.CTkTextbox(
            body,
            height=180,
            corner_radius=18,
            fg_color=COLORS["input"],
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            font=("Segoe UI", 13),
            wrap="word",
        )
        self.prompt_box.pack(fill="x", pady=(0, 10))
        self.bind_prompt_hotkeys()

        self.small_button(body, "Сделать задание коротким и четким", self.enhance_task_prompt).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(body, text="Тип фасада", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        self.facade_mode_menu = ctk.CTkOptionMenu(
            body,
            values=["Авто", "Современный стеклянный фасад", "Классический фасад"],
            variable=self.facade_mode_var,
            height=38,
            corner_radius=15,
            fg_color="#151A20",
            button_color="#252B33",
            button_hover_color="#343B45",
            dropdown_fg_color="#151A20",
            dropdown_hover_color="#252B33",
            text_color=COLORS["text"],
        )
        self.facade_mode_menu.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(body, text="Подготовка для AI", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        self.main_button(
            body,
            "Создать карту света и подготовить файлы для AI",
            lambda: self.generate_package(show_ready_dialog=True),
            height=52,
        ).pack(fill="x", pady=(0, 8))
        self.main_button(
            body,
            "Авто: карта + prompt + Gemini API + рендер",
            self.generate_full_auto_render,
            height=54,
        ).pack(fill="x", pady=(0, 8))

        prep_row = ctk.CTkFrame(body, fg_color="transparent")
        prep_row.pack(fill="x", pady=(0, 16))
        self.small_button(prep_row, "Открыть SEND_TO_AI", self.open_latest).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.small_button(prep_row, "Открыть AI-рабочее место", self.open_ai_workspace).pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(body, text="AI-платформы", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        self.small_button(row, "AI-рабочее место", self.open_ai_workspace).pack(side="left", expand=True, fill="x", padx=(0, 7))
        self.small_button(row, "ChatGPT", lambda: webbrowser.open("https://chatgpt.com/")).pack(side="left", expand=True, fill="x", padx=(0, 7))
        self.small_button(row, "Gemini", lambda: webbrowser.open("https://gemini.google.com/")).pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(body, text="API генерации", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        self.api_provider_menu = ctk.CTkOptionMenu(
            body,
            values=["RouterAI", "Gemini direct"],
            variable=self.api_provider_var,
            height=36,
            corner_radius=14,
            fg_color="#151A20",
            button_color="#252B33",
            button_hover_color="#343B45",
            dropdown_fg_color="#151A20",
            dropdown_hover_color="#252B33",
            text_color=COLORS["text"],
        )
        self.api_provider_menu.pack(fill="x", pady=(0, 8))
        self.routerai_api_key_entry = ctk.CTkEntry(
            body,
            textvariable=self.routerai_api_key_var,
            placeholder_text="ROUTERAI_API_KEY",
            show="*",
            height=36,
            corner_radius=14,
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        self.routerai_api_key_entry.pack(fill="x", pady=(0, 8))
        self.routerai_model_entry = ctk.CTkEntry(
            body,
            textvariable=self.routerai_model_var,
            placeholder_text="google/gemini-2.5-flash-image",
            height=36,
            corner_radius=14,
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        self.routerai_model_entry.pack(fill="x", pady=(0, 8))
        self.api_key_entry = ctk.CTkEntry(
            body,
            textvariable=self.api_key_var,
            placeholder_text="GEMINI_API_KEY для прямого Google API",
            show="*",
            height=36,
            corner_radius=14,
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        self.api_key_entry.pack(fill="x", pady=(0, 8))
        self.gemini_model_entry = ctk.CTkEntry(
            body,
            textvariable=self.gemini_model_var,
            placeholder_text="gemini-2.5-flash-image-preview",
            height=36,
            corner_radius=14,
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        self.gemini_model_entry.pack(fill="x", pady=(0, 8))

        api_row = ctk.CTkFrame(body, fg_color="transparent")
        api_row.pack(fill="x", pady=(0, 16))
        self.small_button(api_row, "Сохранить ключ", self.save_api_settings).pack(side="left", expand=True, fill="x", padx=(0, 7))
        self.small_button(api_row, "Сгенерировать через API", self.generate_with_gemini_api).pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(body, text="Готовый рендер из AI", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 14))
        self.small_button(row2, "Открыть SEND_TO_AI", self.open_latest).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.small_button(row2, "Загрузить\nрезультат из AI", self.import_final_render).pack(side="left", expand=True, fill="x")

        self.edit_prompt_box = ctk.CTkTextbox(
            body,
            height=70,
            corner_radius=14,
            fg_color=COLORS["input"],
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            font=("Segoe UI", 12),
            wrap="word",
        )
        self.edit_prompt_box.pack(fill="x", pady=(0, 8))
        self.edit_prompt_box.insert("1.0", "Убери лишние артефакты и сохрани архитектуру здания.")
        edit_row = ctk.CTkFrame(body, fg_color="transparent")
        edit_row.pack(fill="x", pady=(0, 14))
        self.small_button(edit_row, "Доработать через API", self.edit_final_with_gemini_api).pack(side="left", expand=True, fill="x", padx=(0, 7))
        self.small_button(edit_row, "Открыть в Paint", self.open_final_in_paint).pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(body, text="События проекта", text_color=COLORS["soft"], font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        self.log_box = ctk.CTkTextbox(
            body,
            corner_radius=18,
            fg_color=COLORS["input"],
            border_width=1,
            border_color=COLORS["border"],
            text_color="#DDE2E8",
            font=("Consolas", 11),
            height=145,
        )
        self.log_box.pack(fill="both", expand=True)

    def build_right(self):
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=2, sticky="nsew", padx=(0, 22), pady=(0, 18))
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        card, body = self.card(right, "Просмотр проекта")
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # Переключатель preview: теперь сразу понятно, что именно смотрим.
        tabs = ctk.CTkFrame(body, fg_color="transparent")
        tabs.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tabs.grid_columnconfigure((0, 1, 2), weight=1, uniform="preview_tabs")

        self.preview_buttons["source"] = self.small_button(tabs, "Фото", lambda: self.show_preview("source"))
        self.preview_buttons["source"].grid(row=0, column=0, sticky="ew", padx=(0, 7))

        self.preview_buttons["light"] = self.small_button(tabs, "Карта", lambda: self.show_preview("light"))
        self.preview_buttons["light"].grid(row=0, column=1, sticky="ew", padx=(0, 7))

        self.preview_buttons["final"] = self.small_button(tabs, "Рендер", lambda: self.show_preview("final"))
        self.preview_buttons["final"].grid(row=0, column=2, sticky="ew")

        self.hero_label = ctk.CTkLabel(
            body,
            text="НИТЕОС КОНЦЕПТ СВЕТА\nAI-ПОДГОТОВКА КОНЦЕПЦИЙ",
            corner_radius=24,
            fg_color="#030405",
            text_color=COLORS["muted"],
            font=("Segoe UI", 22, "bold"),
        )
        self.hero_label.grid(row=1, column=0, sticky="nsew")
        self.hero_label.bind("<Configure>", lambda e: self.refresh_hero_fit())

        preview_actions = ctk.CTkFrame(body, fg_color="transparent")
        preview_actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        preview_actions.grid_columnconfigure(0, weight=1)

        self.small_button(
            preview_actions,
            "Открыть SEND_TO_AI",
            self.open_latest,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.main_button(
            preview_actions,
            "Загрузить\nрезультат из AI",
            self.import_final_render,
            height=58,
        ).grid(row=1, column=0, sticky="ew")

        bottom, bottom_body = self.card(right, "Сценарий работы")
        bottom.grid(row=1, column=0, sticky="ew")

        scenario = (
            "1. Загружаем фото фасада и IES.\n"
            "2. Программа готовит карту света, style reference и сильный prompt.\n"
            "3. Проверяем вкладку «Карта» и отправляем SEND_TO_AI в ChatGPT / Gemini.\n"
            "4. Нажимаем «Загрузить результат из AI» и смотрим итог во вкладке «Рендер»."
        )
        ctk.CTkLabel(bottom_body, text=scenario, text_color=COLORS["muted"], font=("Segoe UI", 13), justify="left", anchor="w").pack(fill="x")

    # ---------------------------------------------------------------------
    # State / preview
    # ---------------------------------------------------------------------


    def open_style_reference(self):
        if STYLE_PATH.exists():
            try:
                os.startfile(str(STYLE_PATH))
            except Exception:
                open_folder(REFERENCES_DIR)
        else:
            messagebox.showinfo("Эталон качества", "Эталон качества еще не загружен.")



    def get_light_plan_path(self):
        candidates = [
            OUTPUT_DIR / "latest_light_plan_reference.png",
            EXPORT_DIR / "latest" / "02_light_plan_reference.png",
            EXPORT_DIR / "latest" / "SEND_TO_AI" / "02_light_plan_reference.png",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def get_preview_path(self, mode: str):
        if mode == "source":
            return SOURCE_PATH if SOURCE_PATH.exists() else None
        if mode == "light":
            return self.get_light_plan_path()
        if mode == "final":
            return FINAL_PATH if FINAL_PATH.exists() else None
        return None

    def preview_title(self, mode: str):
        return {
            "source": "Исходное фото еще не загружено",
            "light": "Карта света еще не создана",
            "final": "Результат из AI еще не загружен",
        }.get(mode, "Нет изображения")

    def update_preview_tab_styles(self):
        for mode, btn in self.preview_buttons.items():
            active = mode == self.preview_mode
            try:
                if active:
                    btn.configure(
                        fg_color="#D7DEE8",
                        hover_color="#FFFFFF",
                        text_color="#030405",
                        border_color="#D7DEE8",
                    )
                else:
                    btn.configure(
                        fg_color="#151A20",
                        hover_color="#252B33",
                        text_color=COLORS["text"],
                        border_color=COLORS["border"],
                    )
            except Exception:
                pass

    def show_preview(self, mode: str, silent: bool = False):
        self.preview_mode = mode
        self.update_preview_tab_styles()

        path = self.get_preview_path(mode)
        if path and path.exists():
            self.update_hero(path)
            return

        self.current_hero_path = None
        self.hero_preview = None
        try:
            self.hero_label.configure(image="", text=self.preview_title(mode))
        except Exception:
            self.hero_label.configure(text=self.preview_title(mode))

        if not silent:
            if mode == "light":
                self.log("Карта света еще не создана. Нажмите «Создать читаемую карту света и подготовить».")
            elif mode == "final":
                self.log("Результат из AI еще не загружен.")
            elif mode == "source":
                self.log("Исходное фото еще не загружено.")



    def clear_style_reference(self):
        removed = False
        for path in [
            STYLE_PATH,
            REFERENCES_DIR / "style_reference_target.jpg",
            REFERENCES_DIR / "style_reference_target.jpeg",
            REFERENCES_DIR / "style_reference_target.webp",
        ]:
            try:
                if path.exists():
                    path.unlink()
                    removed = True
            except Exception:
                pass

        try:
            self.style_img_label.configure(image="", text="Можно оставить пустым")
        except Exception:
            self.style_img_label.configure(text="Можно оставить пустым")
        self.style_name_label.configure(text="Эталон качества не выбран")
        self.style_chip.configure(text="Style: нет", text_color=COLORS["red"])
        self.style_preview = None

        if removed:
            self.log("Эталон качества удален из проекта.")
        else:
            self.log("Эталон качества не был выбран.")



    def get_facade_mode_code(self):
        value = self.facade_mode_var.get()
        if value == "Современный стеклянный фасад":
            return "modern_glass"
        if value == "Классический фасад":
            return "classic"
        return "auto"

    def set_facade_mode_from_code(self, code: str):
        code = (code or "auto").strip().lower()
        if code == "modern_glass":
            self.facade_mode_var.set("Современный стеклянный фасад")
        elif code == "classic":
            self.facade_mode_var.set("Классический фасад")
        else:
            self.facade_mode_var.set("Авто")

    def save_facade_mode(self):
        try:
            MODE_PATH.write_text(self.get_facade_mode_code(), encoding="utf-8")
        except Exception:
            pass


    def load_existing(self):
        text = PROMPT_PATH.read_text(encoding="utf-8", errors="ignore").strip() if PROMPT_PATH.exists() else DEFAULT_PROMPT
        self.prompt_box.insert("1.0", self.normalize_prompt_text(text or DEFAULT_PROMPT))
        if MODE_PATH.exists():
            self.set_facade_mode_from_code(MODE_PATH.read_text(encoding="utf-8", errors="ignore"))

        if SOURCE_PATH.exists():
            self.update_source_preview(SOURCE_PATH)
        else:
            self.set_hero_placeholder()

        if STYLE_PATH.exists():
            self.update_style_preview(STYLE_PATH)
        else:
            self.style_chip.configure(text="Style: нет", text_color=COLORS["red"])
            self.style_name_label.configure(text="Эталон качества не выбран")

        self.update_ies_count()
        self.refresh_example_menus()

        if FINAL_PATH.exists():
            self.show_preview("final", silent=True)
        elif SOURCE_PATH.exists():
            self.show_preview("source", silent=True)
        else:
            self.set_hero_placeholder()
            self.update_preview_tab_styles()

        self.log("Интерфейс v1.3.9 загружен: RGBW-формулировка стала нейтральной, без лишних политических уточнений.")


    def clear_old_light_references(self):
        # Старые light-plan файлы могли относиться к предыдущему зданию.
        # При загрузке нового фото очищаем их, чтобы AI не получил чужую схему.
        names = [
            "ai_concept.png",
            "auto_concept.png",
            "concept_demo.png",
            "manual_concept.png",
            "ai_debug_plan.png",
            "auto_debug_bbox.png",
            "latest_light_plan_reference.png",
        ]
        for name in names:
            path = OUTPUT_DIR / name
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass


    def update_source_preview(self, path: Path):
        self.source_preview = make_preview_ctk_image(path, (340, 190))
        self.source_img_label.configure(image=self.source_preview, text="")
        self.source_name_label.configure(text=path.name)
        self.photo_chip.configure(text="Фото: OK", text_color=COLORS["green"])
        self.show_preview("source", silent=True)

    def update_style_preview(self, path: Path):
        # fit-превью: картинка целиком, без сжатия в тонкую полоску
        self.style_preview = make_fit_ctk_image(path, 340, 175, bg="#030405")
        self.style_img_label.configure(image=self.style_preview, text="")
        self.style_name_label.configure(text=path.name)
        self.style_chip.configure(text="Style: OK", text_color=COLORS["green"])

    def update_hero(self, path: Path):
        """
        Показывает изображение целиком в доступной области preview.
        В старой версии стоял минимум 640x420, из-за этого на узком правом блоке
        картинка была больше виджета и обрезалась.
        """
        self.current_hero_path = path

        # Реальные размеры области просмотра.
        label_w = self.hero_label.winfo_width()
        label_h = self.hero_label.winfo_height()

        # Если виджет еще не отрисован, берем безопасные значения.
        if label_w < 100:
            label_w = 520
        if label_h < 100:
            label_h = 520

        # Небольшие поля внутри черной карточки.
        box_w = max(180, label_w - 28)
        box_h = max(180, label_h - 28)

        self.hero_preview = make_fit_ctk_image(path, box_w, box_h, bg="#030405")
        self.hero_label.configure(image=self.hero_preview, text="")


    def refresh_hero_fit(self):
        if self.current_hero_path and Path(self.current_hero_path).exists():
            try:
                self.update_hero(Path(self.current_hero_path))
            except Exception:
                pass
        else:
            try:
                self.update_preview_tab_styles()
            except Exception:
                pass

    def set_hero_placeholder(self):
        self.current_hero_path = None
        label_w = getattr(self, "hero_label", None).winfo_width() if hasattr(self, "hero_label") else 780
        label_h = getattr(self, "hero_label", None).winfo_height() if hasattr(self, "hero_label") else 520
        if label_w < 100:
            label_w = 520
        if label_h < 100:
            label_h = 420
        img = make_noir_placeholder(max(260, label_w - 28), max(240, label_h - 28))
        self.hero_preview = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.hero_label.configure(image=self.hero_preview, text="")


    def update_ies_count(self):
        n = count_ies()
        if n:
            self.ies_label.configure(text=f"Загружено IES: {n}\nРежим: концепция с учетом IES")
            self.ies_chip.configure(text=f"IES: {n}", text_color=COLORS["green"])
        else:
            self.ies_label.configure(text="IES: нет\nРежим: визуальная концепция без IES")
            self.ies_chip.configure(text="IES: нет / визуальный режим", text_color=COLORS["gold"])
        return n

    def refresh_example_menus(self):
        self.refresh_source_examples()
        self.refresh_style_examples()

    def refresh_source_examples(self):
        paths = []
        paths.extend(image_files_in(INPUT_DIR, recursive=False))
        paths.extend(image_files_in(SOURCE_EXAMPLES_DIR, recursive=True))
        paths = [p for p in paths if p.resolve() != SOURCE_PATH.resolve()]
        self.source_example_paths = unique_display_paths(paths)
        values = list(self.source_example_paths.keys()) or ["Примеры: нет файлов"]
        if hasattr(self, "source_example_menu"):
            self.source_example_menu.configure(values=values)
            self.source_example_menu.set("Выбрать фото из папки" if self.source_example_paths else "Примеры: нет файлов")

    def refresh_style_examples(self):
        paths = []
        paths.extend(image_files_in(REFERENCES_DIR, recursive=False))
        paths.extend(image_files_in(STYLE_EXAMPLES_DIR, recursive=True))
        paths = [p for p in paths if p.resolve() != STYLE_PATH.resolve()]
        self.style_example_paths = unique_display_paths(paths)
        values = list(self.style_example_paths.keys()) or ["Примеры: нет файлов"]
        if hasattr(self, "style_example_menu"):
            self.style_example_menu.configure(values=values)
            self.style_example_menu.set("Выбрать style reference" if self.style_example_paths else "Примеры: нет файлов")

    def select_source_example(self, label):
        path = self.source_example_paths.get(label)
        if not path:
            self.refresh_source_examples()
            return
        try:
            save_rgb(path, SOURCE_PATH)
            self.clear_old_light_references()
            self.update_source_preview(SOURCE_PATH)
            self.refresh_source_examples()
            self.log(f"Фото выбрано из примеров: {path.name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выбрать фото из примеров:\n{e}")

    def select_style_example(self, label):
        path = self.style_example_paths.get(label)
        if not path:
            self.refresh_style_examples()
            return
        try:
            save_rgb(path, STYLE_PATH)
            self.update_style_preview(STYLE_PATH)
            self.refresh_style_examples()
            self.log(f"Style reference выбран из примеров: {path.name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выбрать style reference:\n{e}")

    def load_ies_examples(self):
        files = ies_files_in(IES_EXAMPLES_DIR, recursive=True)
        if not files:
            messagebox.showinfo(
                "IES-примеры",
                f"Положите .ies файлы или папки с .ies сюда:\n{IES_EXAMPLES_DIR}"
            )
            open_folder(IES_EXAMPLES_DIR)
            return
        self.copy_ies_files_to_library(files, "IES-примеры загружены")

    def log(self, text):
        t = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{t}] {text}\n")
        self.log_box.see("end")


    def build_enhanced_task(self, raw_text: str) -> str:
        raw = self.normalize_prompt_text(raw_text)
        if not raw:
            raw = DEFAULT_PROMPT

        low = raw.lower()

        is_flag = (
            "флаг" in low
            or "триколор" in low
            or ("бел" in low and "син" in low and "крас" in low)
        )
        is_rgbw = "rgb" in low or "rgbw" in low

        if is_flag:
            return (
                "Линейная RGBW-подсветка в логике флага России: "
                "верхние ряды — белым, средние — синим, нижние — красным. "
                "Цвета должны идти по архитектурным линиям и членениям фасада, без плоской раскраски. "
                f"Исходное описание: {raw}"
            )

        if is_rgbw:
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
        elif any(w in low for w in ["пилястр", "колон", "простен", "вертик", "луч", "прожектор", "серед"]):
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
            f"Исходное описание: {raw}"
        )

    def enhance_task_prompt(self):
        raw = self.normalize_prompt_text(self.prompt_box.get("1.0", "end"))
        enhanced = self.build_enhanced_task(raw)

        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", enhanced)
        PROMPT_PATH.write_text(enhanced, encoding="utf-8")
        self.log("Задание сжато: оставлена короткая и четкая логика для AI.")


    def get_upload_to_ai_dir(self):
        latest = EXPORT_DIR / "latest"
        upload = latest / "SEND_TO_AI"
        if upload.exists():
            return upload
        return latest


    def open_ai_workspace(self):
        latest = EXPORT_DIR / "latest"
        if not latest.exists():
            answer = messagebox.askyesno(
                "Нет подготовленных файлов",
                "Папка latest еще не создана. Сначала подготовить файлы для AI?"
            )
            if answer:
                self.generate_package(False)
            return

        prompt_file = latest / "04_prompt_for_chatgpt.txt"
        if prompt_file.exists():
            copy_text_to_clipboard(prompt_file.read_text(encoding="utf-8", errors="ignore"))

        open_folder(self.get_upload_to_ai_dir())
        AIWorkspaceDialog(self, latest)


    def save_api_settings(self):
        try:
            provider = "routerai" if self.api_provider_var.get() == "RouterAI" else "gemini"
            save_api_provider(provider)
            save_routerai_settings(self.routerai_api_key_var.get(), self.routerai_model_var.get())
            save_gemini_settings(self.api_key_var.get(), self.gemini_model_var.get())
            self.log(f"API-настройки сохранены. Провайдер: {self.api_provider_var.get()}.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить API-настройки:\n{e}")

    def ensure_latest_package(self, force_rebuild=False):
        latest = EXPORT_DIR / "latest"
        prompt_file = latest / "04_prompt_for_chatgpt.txt"
        if not force_rebuild and latest.exists() and prompt_file.exists():
            return latest
        self.generate_package(show_ready_dialog=False)
        if latest.exists() and prompt_file.exists():
            return latest
        raise RuntimeError("Не удалось подготовить latest-пакет для AI.")

    def run_api_worker(self, title, target, on_success):
        self.save_api_settings()
        self.log(f"{title}: запрос отправлен...")

        def worker():
            try:
                result_path = target()
                self.after(0, lambda: on_success(result_path))
            except Exception as e:
                self.after(0, lambda: self.api_error(title, e))

        threading.Thread(target=worker, daemon=True).start()

    def api_error(self, title, error):
        self.log(f"{title}: ошибка API: {error}")
        messagebox.showerror("Gemini API", f"{title} не выполнен:\n{error}")

    def generate_with_gemini_api(self):
        if not SOURCE_PATH.exists():
            messagebox.showwarning("Нет фото", "Сначала загрузите фото фасада.")
            return
        try:
            latest = self.ensure_latest_package(force_rebuild=True)
        except Exception as e:
            messagebox.showerror("Gemini API", f"Не удалось подготовить пакет для API:\n{e}")
            return

        def task():
            prompt_file = latest / "05_prompt_for_gemini_nano_banana.txt"
            if not prompt_file.exists():
                prompt_file = latest / "04_prompt_for_chatgpt.txt"
            prompt = prompt_file.read_text(encoding="utf-8", errors="ignore")
            image_paths = [
                latest / "01_source_building.png",
                latest / "02_light_plan_reference.png",
            ]
            style_path = latest / "03_style_reference_target.png"
            if style_path.exists():
                image_paths.append(style_path)
            provider = "routerai" if self.api_provider_var.get() == "RouterAI" else "gemini"
            return call_selected_image_api(
                provider,
                prompt,
                image_paths,
                API_FINAL_PATH,
                gemini_key=self.api_key_var.get(),
                gemini_model=self.gemini_model_var.get(),
                routerai_key=self.routerai_api_key_var.get(),
                routerai_model=self.routerai_model_var.get(),
            )

        def done(path):
            save_rgb(path, FINAL_PATH)
            self.show_preview("final", silent=True)
            self.log(f"{self.api_provider_var.get()}: рендер сохранен: {FINAL_PATH.name}")

        self.run_api_worker(f"{self.api_provider_var.get()} генерация", task, done)

    def generate_full_auto_render(self):
        self.generate_with_gemini_api()

    def edit_final_with_gemini_api(self):
        if not FINAL_PATH.exists():
            messagebox.showwarning("Нет рендера", "Сначала загрузите или сгенерируйте финальный рендер.")
            return
        instruction = self.normalize_prompt_text(self.edit_prompt_box.get("1.0", "end"))
        if not instruction:
            messagebox.showwarning("Нет задания", "Напишите, что изменить в результате.")
            return

        def task():
            prompt = (
                "Edit this architectural lighting render according to the instruction. "
                "Preserve building geometry, facade materials, windows and realistic night lighting. "
                f"Instruction: {instruction}"
            )
            provider = "routerai" if self.api_provider_var.get() == "RouterAI" else "gemini"
            return call_selected_image_api(
                provider,
                prompt,
                [FINAL_PATH],
                API_EDITED_PATH,
                gemini_key=self.api_key_var.get(),
                gemini_model=self.gemini_model_var.get(),
                routerai_key=self.routerai_api_key_var.get(),
                routerai_model=self.routerai_model_var.get(),
            )

        def done(path):
            save_rgb(path, FINAL_PATH)
            self.show_preview("final", silent=True)
            self.log(f"{self.api_provider_var.get()}: рендер доработан: {FINAL_PATH.name}")

        self.run_api_worker(f"{self.api_provider_var.get()} доработка", task, done)

    def open_final_in_paint(self):
        if not FINAL_PATH.exists():
            messagebox.showwarning("Нет рендера", "Сначала загрузите или сгенерируйте финальный рендер.")
            return
        try:
            subprocess.Popen(["mspaint", str(FINAL_PATH)])
            self.log("Финальный рендер открыт в Paint.")
        except Exception as e:
            messagebox.showerror("Paint", f"Не удалось открыть Paint:\n{e}")



    def prompt_text_widget(self):
        return getattr(self.prompt_box, "_textbox", self.prompt_box)

    def prompt_has_focus(self):
        try:
            focused = self.focus_get()
            widget = self.prompt_text_widget()
            return focused == widget or focused == self.prompt_box
        except Exception:
            return False

    def select_all_prompt(self, event=None):
        try:
            widget = self.prompt_text_widget()
            widget.focus_set()
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
        except Exception:
            pass
        return "break"

    def copy_prompt_selection(self, event=None):
        try:
            widget = self.prompt_text_widget()
            text = widget.get("sel.first", "sel.last")
            copy_text_to_clipboard(text)
        except Exception:
            pass
        return "break"

    def cut_prompt_selection(self, event=None):
        try:
            widget = self.prompt_text_widget()
            text = widget.get("sel.first", "sel.last")
            copy_text_to_clipboard(text)
            widget.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def paste_prompt_clipboard(self, event=None):
        try:
            widget = self.prompt_text_widget()
            txt = self.clipboard_get()
            widget.insert("insert", txt)
        except Exception:
            pass
        return "break"

    def normalize_prompt_text(self, value: str) -> str:
        # Если в поле случайно попали буквальные \\n, превращаем их в нормальные переносы.
        return (value or "").replace("\\\\n", "\\n").strip()

    def prompt_hotkey_dispatch(self, event):
        # Универсальная обработка Ctrl+A/C/X/V именно для поля задания.
        # Работает надежнее, чем отдельные бинды CTkTextbox.
        if not self.prompt_has_focus():
            return None

        ctrl_pressed = bool(event.state & 0x4)
        if not ctrl_pressed:
            return None

        keysym = (getattr(event, "keysym", "") or "").lower()
        char = (getattr(event, "char", "") or "").lower()
        keycode = getattr(event, "keycode", None)

        # Windows keycode: A=65, C=67, V=86, X=88.
        if keysym in ("a", "ф") or char in ("a", "ф") or keycode == 65:
            return self.select_all_prompt(event)
        if keysym in ("c", "с") or char in ("c", "с") or keycode == 67:
            return self.copy_prompt_selection(event)
        if keysym in ("x", "ч") or char in ("x", "ч") or keycode == 88:
            return self.cut_prompt_selection(event)
        if keysym in ("v", "м") or char in ("v", "м") or keycode == 86:
            return self.paste_prompt_clipboard(event)

        return None

    def bind_prompt_hotkeys(self):
        # Привязка напрямую к внутреннему Text + глобальный перехват.
        # Это закрывает проблему, когда CTkTextbox съедает Ctrl+A.
        widget = self.prompt_text_widget()

        for key, func in {
            "<Control-a>": self.select_all_prompt,
            "<Control-A>": self.select_all_prompt,
            "<Control-KeyPress-a>": self.select_all_prompt,
            "<Control-KeyPress-A>": self.select_all_prompt,
            "<Control-KeyPress-ф>": self.select_all_prompt,
            "<Control-KeyPress-Ф>": self.select_all_prompt,
            "<Control-c>": self.copy_prompt_selection,
            "<Control-C>": self.copy_prompt_selection,
            "<Control-x>": self.cut_prompt_selection,
            "<Control-X>": self.cut_prompt_selection,
            "<Control-v>": self.paste_prompt_clipboard,
            "<Control-V>": self.paste_prompt_clipboard,
        }.items():
            try:
                self.prompt_box.bind(key, func, add="+")
                widget.bind(key, func, add="+")
            except Exception:
                pass

        try:
            self.bind_all("<KeyPress>", self.prompt_hotkey_dispatch, add="+")
        except Exception:
            pass


    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------

    def load_source_photo(self):
        file = filedialog.askopenfilename(title="Выберите фото фасада", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not file:
            return
        try:
            save_rgb(Path(file), SOURCE_PATH)
            self.clear_old_light_references()
            self.update_source_preview(SOURCE_PATH)
            self.refresh_source_examples()
            self.log(f"Фото загружено: {Path(file).name}")
            self.log("Для этого здания новая черновая карта будет создана автоматически при подготовке файлов для AI.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить фото:\n{e}")

    def load_style_reference(self):
        file = filedialog.askopenfilename(title="Выберите новый эталон качества / style reference", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not file:
            return
        try:
            save_rgb(Path(file), STYLE_PATH)
            self.update_style_preview(STYLE_PATH)
            self.refresh_style_examples()
            self.log(f"Эталон качества заменен: {Path(file).name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить эталон:\n{e}")

    def copy_ies_files_to_library(self, files, done_label="IES загружены"):
        for old in ies_files_in(IES_DIR, recursive=False):
            try:
                old.unlink()
            except Exception:
                pass

        copied = 0
        used_names = set()
        for f in files:
            try:
                target_name = f.name
                stem = f.stem
                suffix = f.suffix

                index = 2
                while target_name.lower() in used_names or (IES_DIR / target_name).exists():
                    target_name = f"{stem}_{index}{suffix}"
                    index += 1

                shutil.copy2(f, IES_DIR / target_name)
                used_names.add(target_name.lower())
                copied += 1
            except Exception as e:
                self.log(f"Не удалось скопировать {f.name}: {e}")

        self.update_ies_count()
        self.log(f"{done_label}: {copied}. Текущий счетчик: {count_ies()}")
        return copied

    def load_ies_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с IES")
        if not folder:
            return

        src_dir = Path(folder)
        files = ies_files_in(src_dir, recursive=True)
        if not files:
            messagebox.showwarning("IES не найдены", "В выбранной папке и ее подпапках нет .ies файлов.")
            self.update_ies_count()
            return

        # Если пользователь выбрал саму рабочую папку ies_library,
        # ничего не удаляем и не копируем — просто обновляем счетчик.
        try:
            same_as_library = src_dir.resolve() == IES_DIR.resolve()
        except Exception:
            same_as_library = False

        if same_as_library:
            self.update_ies_count()
            self.log(f"IES обновлены в рабочей папке: {count_ies()}")
            return

        # При загрузке новой папки старые IES удаляем, чтобы счетчик и prompt
        # соответствовали именно текущему набору файлов.
        self.copy_ies_files_to_library(files)

    def new_project(self):
        ok = messagebox.askyesno(
            "Создать новый проект",
            "Очистить текущее фото, финальный рендер и latest-пакет?\n\nIES-файлы и эталон качества останутся."
        )
        if not ok:
            return

        for path in [SOURCE_PATH, FINAL_PATH]:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

        latest = EXPORT_DIR / "latest"
        if latest.exists():
            try:
                shutil.rmtree(latest)
            except Exception:
                pass

        self.source_img_label.configure(image=None, text="Загрузите фото")
        self.source_name_label.configure(text="Файл не выбран")
        self.photo_chip.configure(text="Фото: нет", text_color=COLORS["red"])
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", DEFAULT_PROMPT)
        self.facade_mode_var.set("Авто")
        self.save_facade_mode()
        self.preview_mode = "source"
        self.set_hero_placeholder()
        self.update_preview_tab_styles()
        self.log("Создан новый проект. IES и эталон качества сохранены.")

    def generate_package(self, show_ready_dialog=True):
        prompt = self.normalize_prompt_text(self.prompt_box.get("1.0", "end"))
        if not prompt:
            messagebox.showwarning("Нет задания", "Введите задание для подсветки.")
            return

        if not SOURCE_PATH.exists():
            messagebox.showwarning("Нет фото", "Сначала загрузите фото фасада.")
            return

        PROMPT_PATH.write_text(prompt, encoding="utf-8")
        self.save_facade_mode()
        self.log(f"Тип фасада: {self.facade_mode_var.get()}")
        if self.get_facade_mode_code() == "modern_glass":
            self.log("Режим современного стеклянного фасада: используем отдельную логику карты света.")

        if count_ies() == 0:
            self.log("IES не загружены: работаем в визуальном режиме без привязки к светильникам.")

        try:
            self.log("Учитываю IES/КСС и создаю короткий четкий prompt для AI...")

            # В исходниках и в .exe сборщик запускается напрямую как Python-модуль.
            # Так собранная программа не требует установленного Python на компьютере пользователя.
            packager_module = importlib.import_module("ai_packager_v29")

            buffer = io.StringIO()
            old_cwd = os.getcwd()
            try:
                os.chdir(str(BASE_DIR))
                with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                    packager_module.main()
            finally:
                os.chdir(old_cwd)

            output_text = buffer.getvalue().strip()
            if output_text:
                last_line = output_text.splitlines()[-1]
                self.log(last_line)

            latest = EXPORT_DIR / "latest"
            self.log("Файлы для AI готовы: project_export/latest")
            self.show_preview("light", silent=True)
            if show_ready_dialog:
                ReadyDialog(self, latest)

        except Exception as e:
            details = buffer.getvalue().strip() if "buffer" in locals() else ""
            if details:
                details = f"{e}\n\nПодробности:\n{details}"
            else:
                details = str(e)
            messagebox.showerror("Ошибка", f"Не удалось сформировать пакет:\n{details}")
            self.log(f"Ошибка генерации пакета: {details}")

    def open_latest(self):
        latest = EXPORT_DIR / "latest"
        upload = latest / "SEND_TO_AI"
        if upload.exists():
            open_folder(upload)
        elif latest.exists():
            open_folder(latest)
        else:
            messagebox.showwarning("Нет файлов для AI", "Сначала подготовьте файлы для AI.")

    def import_final_render(self):
        file = filedialog.askopenfilename(title="Выберите финальную картинку от AI", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not file:
            return
        try:
            save_rgb(Path(file), FINAL_PATH)
            self.show_preview("final", silent=True)
            self.log(f"Результат из AI загружен: {Path(file).name}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать финальный рендер:\n{e}")


def main():
    app = App()
    app.withdraw()
    splash = Splash(app)

    def show_main():
        try:
            splash.destroy()
        except Exception:
            pass
        app.deiconify()
        app.lift()
        app.focus_force()

    app.after(2000, show_main)
    app.mainloop()


if __name__ == "__main__":
    main()
