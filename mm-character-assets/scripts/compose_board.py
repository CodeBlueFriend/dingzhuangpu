#!/usr/bin/env python3
"""Compose passed view assets into a deterministic labeled PNG board."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    print("Pillow is required. Install with: python -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)

LABELS = {
    "front": "正面 FRONT", "left_profile": "角色左侧 LEFT", "back": "背面 BACK",
    "right_profile": "角色右侧 RIGHT", "left_three_quarter": "左前 3/4",
    "right_three_quarter": "右前 3/4",
}


def _font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _fit(image: Image.Image, box: tuple[int, int], background=(248, 246, 242)) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail(box, Image.Resampling.LANCZOS)
    cell = Image.new("RGB", box, background)
    cell.paste(image, ((box[0] - image.width) // 2, (box[1] - image.height) // 2))
    return cell


def compose(spec: dict, base: Path, output: Path, width: int | None = None) -> tuple[int, int]:
    tasks = [t for t in spec["view_tasks"] if t.get("status") == "succeeded" and t.get("qa_result") == "pass" and t.get("asset_path")]
    wanted = list(spec["board"]["body_views"])
    body = []
    for view in wanted:
        matches = [t for t in tasks if t.get("framing") == "full_body" and t.get("view_id") == view]
        if not matches:
            raise ValueError(f"missing passed full-body task for {view}")
        body.append(matches[0])
    extras = [t for t in tasks if t.get("framing") in {"face", "detail"}]

    target_w, target_h = spec["board"].get("target_canvas", [4096, 3072])
    if width:
        ratio = width / target_w
        target_w, target_h = width, max(1, round(target_h * ratio))
    margin = max(24, target_w // 80)
    header = max(100, target_h // 10)
    gap = max(16, target_w // 160)
    body_fraction = 0.76 if not extras else 0.67
    body_h = int((target_h - header - 2 * margin) * body_fraction)
    body_w = (target_w - 2 * margin - gap * (len(body) - 1)) // len(body)

    canvas = Image.new("RGB", (target_w, target_h), (238, 235, 229))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(max(26, target_w // 85))
    label_font = _font(max(18, target_w // 150))
    title = f"定妆谱 · {spec['character_id']} · {spec['look_id']} v{spec['look_version']}"
    draw.text((margin, margin), title, fill=(55, 48, 43), font=title_font)

    y = header
    for index, task in enumerate(body):
        x = margin + index * (body_w + gap)
        path = Path(task["asset_path"])
        if not path.is_absolute():
            path = base / path
        with Image.open(path) as image:
            cell = _fit(image, (body_w, body_h))
        canvas.paste(cell, (x, y))
        draw.rectangle((x, y, x + body_w, y + body_h), outline=(180, 172, 161), width=max(2, target_w // 2048))
        draw.text((x + 12, y + 10), LABELS.get(task["view_id"], task["view_id"]), fill=(55, 48, 43), font=label_font)

    if extras:
        extra_y = y + body_h + gap
        extra_h = target_h - extra_y - margin
        extra_w = (target_w - 2 * margin - gap * (len(extras) - 1)) // len(extras)
        for index, task in enumerate(extras):
            x = margin + index * (extra_w + gap)
            path = Path(task["asset_path"])
            if not path.is_absolute():
                path = base / path
            with Image.open(path) as image:
                cell = _fit(image, (extra_w, extra_h))
            canvas.paste(cell, (x, extra_y))
            draw.rectangle((x, extra_y, x + extra_w, extra_y + extra_h), outline=(180, 172, 161), width=max(2, target_w // 2048))
            draw.text((x + 10, extra_y + 8), LABELS.get(task["view_id"], task["view_id"]), fill=(55, 48, 43), font=label_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    return canvas.size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, help="optional preview width; preserves target aspect ratio")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        size = compose(spec, args.spec.parent, args.output, args.width)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"composition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "actual_canvas": list(size)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
