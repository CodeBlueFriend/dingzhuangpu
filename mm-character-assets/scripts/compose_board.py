#!/usr/bin/env python3
"""Compose passed assets into a V1.2 horizontal, white-framed PNG board."""

from __future__ import annotations

import argparse
import json
import math
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
    "right_three_quarter": "右前 3/4", "eyes_brows": "眉眼", "nose_lips": "鼻唇",
    "footwear_three_quarter": "鞋履斜前", "footwear_profile": "鞋履侧面",
    "hair_back": "后发型", "neckline": "领口", "waist_or_hem": "腰线/下摆", "cuff": "袖口",
}


def _font(size: int):
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid RGB color: {value}")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _fit(image: Image.Image, box: tuple[int, int], background: tuple[int, int, int], align: str = "center") -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail(box, Image.Resampling.LANCZOS)
    cell = Image.new("RGB", box, background)
    x = (box[0] - image.width) // 2
    y = box[1] - image.height if align == "bottom" else (box[1] - image.height) // 2
    cell.paste(image, (x, y))
    return cell


def _task_for(tasks: list[dict], framing: str, asset_id: str) -> dict:
    matches = [
        task for task in tasks
        if task.get("framing") == framing
        and (task.get("detail_id") == asset_id or task.get("view_id") == asset_id)
    ]
    if not matches:
        raise ValueError(f"missing passed {framing} task for {asset_id}")
    return matches[0]


def _rect(x: int, y: int, width: int, height: int) -> dict[str, int]:
    return {"x": x, "y": y, "width": width, "height": height}


def _grid(rect: dict[str, int], count: int, columns: int, gap: int) -> list[dict[str, int]]:
    if count == 0:
        return []
    rows = math.ceil(count / columns)
    cell_w = (rect["width"] - gap * (columns - 1)) // columns
    cell_h = (rect["height"] - gap * (rows - 1)) // rows
    cells = []
    for index in range(count):
        col, row = index % columns, index // columns
        width = cell_w if col < columns - 1 else rect["width"] - col * (cell_w + gap)
        height = cell_h if row < rows - 1 else rect["height"] - row * (cell_h + gap)
        cells.append(_rect(rect["x"] + col * (cell_w + gap), rect["y"] + row * (cell_h + gap), width, height))
    return cells


def _layout(spec: dict, target_w: int, target_h: int) -> dict:
    board = spec["board"]
    if target_w <= target_h:
        raise ValueError("V1.2 board must be landscape")
    expected_h = round(target_w * board.get("aspect_ratio", [16, 9])[1] / board.get("aspect_ratio", [16, 9])[0])
    if abs(target_h - expected_h) > 1:
        raise ValueError("target canvas must match the planned aspect ratio")

    source_w, source_h = board.get("target_canvas", [6144, 3456])
    scale = target_w / source_w
    frame = max(1, round(board.get("outer_frame", {}).get("width_px", 72) * scale))
    column_gap = max(1, round(32 * target_w / 6144))
    cell_gap = max(1, round(24 * target_w / 6144))
    title_h = max(24, round(80 * target_h / 3456))
    footer_h = max(18, round(64 * target_h / 3456))
    inner = _rect(frame, frame, target_w - 2 * frame, target_h - 2 * frame)
    content = _rect(inner["x"], inner["y"] + title_h, inner["width"], inner["height"] - title_h - footer_h)
    ratios = board.get("region_width_ratios", [0.46, 0.24, 0.30])
    net_width = content["width"] - 2 * column_gap
    # Use the V1.2 reference geometry as the precise implementation of the rounded 46/24/30 design ratios.
    if ratios == [0.46, 0.24, 0.30]:
        left_w = round(net_width * 2736 / 5936)
        middle_w = round(net_width * 1424 / 5936)
    else:
        left_w = round(net_width * ratios[0])
        middle_w = round(net_width * ratios[1])
    right_w = net_width - left_w - middle_w
    left = _rect(content["x"], content["y"], left_w, content["height"])
    middle = _rect(left["x"] + left_w + column_gap, content["y"], middle_w, content["height"])
    right = _rect(middle["x"] + middle_w + column_gap, content["y"], right_w, content["height"])

    body_count = len(board["body_views"])
    face_count = len(board.get("face_views", []))
    detail_count = len(board.get("detail_ids", []))
    if spec["inputs"].get("board_content") == "body_only":
        left = content
        middle = _rect(content["x"] + content["width"], content["y"], 0, content["height"])
        right = middle.copy()
    return {
        "orientation": "landscape",
        "aspect_ratio": board.get("aspect_ratio", [16, 9]),
        "canvas_size": [target_w, target_h],
        "frame_width": frame,
        "frame_color": board.get("outer_frame", {}).get("color", "#FFFFFF"),
        "inner_background": board.get("inner_background", "#F4F5F6"),
        "title_rect": _rect(inner["x"], inner["y"], inner["width"], title_h),
        "footer_rect": _rect(inner["x"], inner["y"] + inner["height"] - footer_h, inner["width"], footer_h),
        "region_rects": {"body": left, "face": middle, "detail": right},
        "cell_rects": {
            "body": _grid(left, body_count, max(1, body_count), cell_gap),
            "face": _grid(middle, face_count, 1, cell_gap),
            "detail": _grid(right, detail_count, 2, cell_gap),
        },
        "cell_labels": [*board["body_views"], *board.get("face_views", []), *board.get("detail_ids", [])],
        "source_asset_ids": [],
        "fit_mode": {"body": "contain_bottom", "face": "contain", "detail": "contain"},
    }


def compose(spec: dict, base: Path, output: Path, width: int | None = None) -> tuple[int, int]:
    tasks = [task for task in spec["view_tasks"] if task.get("status") == "succeeded" and task.get("qa_result") == "pass" and task.get("asset_path")]
    board = spec["board"]
    body = [_task_for(tasks, "full_body", view) for view in board["body_views"]]
    faces = [_task_for(tasks, "face", view) for view in board.get("face_views", [])]
    details = [_task_for(tasks, "detail", detail_id) for detail_id in board.get("detail_ids", [])]

    target_w, target_h = board.get("target_canvas", [6144, 3456])
    if width:
        target_w = width
        ratio = board.get("aspect_ratio", [16, 9])
        target_h = round(width * ratio[1] / ratio[0])
    layout = _layout(spec, target_w, target_h)
    frame_color = _hex_color(layout["frame_color"])
    inner_color = _hex_color(layout["inner_background"])
    canvas = Image.new("RGB", (target_w, target_h), frame_color)
    frame = layout["frame_width"]
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((frame, frame, target_w - frame - 1, target_h - frame - 1), fill=inner_color)
    title_font = _font(max(16, target_w // 180))
    label_font = _font(max(11, target_w // 300))
    title = f"定妆谱 · {spec['character_id']} · {spec['look_id']} v{spec['look_version']}"
    title_rect = layout["title_rect"]
    draw.text((title_rect["x"] + 12, title_rect["y"] + 4), title, fill=(55, 48, 43), font=title_font)

    groups = [(body, "body"), (faces, "face"), (details, "detail")]
    for group, name in groups:
        for task, rect in zip(group, layout["cell_rects"][name]):
            path = Path(task["asset_path"])
            if not path.is_absolute():
                path = base / path
            with Image.open(path) as image:
                cell = _fit(image, (rect["width"], rect["height"]), inner_color, "bottom" if name == "body" else "center")
            canvas.paste(cell, (rect["x"], rect["y"]))
            asset_id = task.get("detail_id") or task.get("view_id") or task["task_id"]
            layout["source_asset_ids"].append(task["task_id"])
            draw.text((rect["x"] + 6, rect["y"] + 4), LABELS.get(asset_id, asset_id), fill=(55, 48, 43), font=label_font)

    footer = layout["footer_rect"]
    draw.text((footer["x"] + 12, footer["y"] + 2), f"identity v{spec['identity_version']} · board v{spec['board_version']} · {board.get('detail_level', 'enhanced')}", fill=(80, 75, 70), font=label_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    manifest = output.with_suffix(".layout.json")
    manifest.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return canvas.size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, help="optional preview width; preserves the planned aspect ratio")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        size = compose(spec, args.spec.parent, args.output, args.width)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"composition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "layout_manifest": str(args.output.with_suffix('.layout.json')), "actual_canvas": list(size)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
