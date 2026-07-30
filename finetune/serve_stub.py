# -*- coding: utf-8 -*-
"""Minimal stub server for FINETUNED_IMAGE_API_URL contract testing."""
from __future__ import annotations

import argparse
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/health"):
            self._json(200, {"ok": True, "service": "niteos-finetune-stub"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/v1/images/generate":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        prompt = str(body.get("prompt") or "")[:80]
        img = Image.new("RGB", (1024, 576), (18, 24, 32))
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 40, 984, 536), outline=(245, 185, 66), width=3)
        draw.text((60, 60), "NITEOS LoRA stub", fill=(245, 185, 66))
        draw.text((60, 100), prompt or "(empty prompt)", fill=(220, 230, 240))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self._json(200, {
            "image": f"data:image/png;base64,{b64}",
            "lora_id": body.get("lora_id"),
            "model": body.get("model"),
        })

    def log_message(self, fmt: str, *args) -> None:
        print(f"[finetune-stub] {args[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Fine-tune stub listening on http://{args.host}:{args.port}")
    print("Set FINETUNED_IMAGE_API_URL=http://127.0.0.1:8091")
    server.serve_forever()


if __name__ == "__main__":
    main()
