#!/usr/bin/env python3
"""Compose passed assets into a V1.3 top-views/bottom-details board."""

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

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"


def _catalog() -> dict:
    return json.loads((ASSET_DIR / "label-catalog.json").read_text(encoding="utf-8"))


def _font(size: int) -> tuple[ImageFont.FreeTypeFont, str]:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size), candidate
            except OSError:
                pass
    raise ValueError("no Chinese-capable font found; refusing to emit garbled V1.3 labels")


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
    matches = [task for task in tasks if task.get("framing") == framing and (task.get("detail_id") == asset_id or task.get("view_id") == asset_id)]
    if not matches:
        raise ValueError(f"missing passed {framing} task for {asset_id}")
    return matches[0]


def _rect(x: int, y: int, width: int, height: int) -> dict[str, int]:
    return {"x": x, "y": y, "width": width, "height": height}


def _split(rect: dict[str, int], count: int, gap: int) -> list[dict[str, int]]:
    if count <= 0:
        return []
    base = (rect["width"] - gap * (count - 1)) // count
    cells = []
    for index in range(count):
        x = rect["x"] + index * (base + gap)
        width = base if index < count - 1 else rect["x"] + rect["width"] - x
        cells.append(_rect(x, rect["y"], width, rect["height"]))
    return cells


def _cell(cell_id: str, total: dict[str, int], label_h: int, view_id: str | None = None, part_id: str | None = None) -> dict:
    return {"cell_id": cell_id, "view_id": view_id, "part_id": part_id,
            "rect": _rect(total["x"], total["y"], total["width"], total["height"] - label_h),
            "label_rect": _rect(total["x"], total["y"] + total["height"] - label_h, total["width"], label_h)}


def _scaled(value: int, target_w: int) -> int:
    return max(1, round(value * target_w / 6144))


def _layout(spec: dict, target_w: int, target_h: int) -> dict:
    board = spec["board"]
    if target_w <= target_h or abs(target_h - round(target_w * 9 / 16)) > 1:
        raise ValueError("V1.3 canvas must be landscape 16:9")
    frame = max(1, round(board["outer_frame"]["width_px"] * target_w / board.get("target_canvas", [6144])[0]))
    gap, major_gap = _scaled(24, target_w), _scaled(32, target_w)
    title_h, section_h, footer_h = (_scaled(v, target_w) for v in (96, 48, 64))
    section_gap = _scaled(16, target_w)
    label_h = max(18, round(board["labels"].get("cell_label_height_px", 48) * target_w / 6144))
    inner = _rect(frame, frame, target_w - 2 * frame, target_h - 2 * frame)
    title = _rect(inner["x"], inner["y"], inner["width"], title_h)
    footer = _rect(inner["x"], inner["y"] + inner["height"] - footer_h, inner["width"], footer_h)
    content_y = title["y"] + title_h + gap
    content_h = footer["y"] - gap - content_y
    body_only = spec["inputs"].get("board_content") == "body_only"
    if body_only:
        body_region = _rect(inner["x"], content_y, inner["width"], content_h)
        face_region = detail_region = _rect(inner["x"] + inner["width"], content_y, 0, 0)
    else:
        height_ratios = board.get("content_height_ratios", [0.685, 0.315])
        upper_h = round((content_h - major_gap) * height_ratios[0])
        detail_h = content_h - major_gap - upper_h
        upper_net_w = inner["width"] - major_gap
        ratios = board.get("upper_region_width_ratios", [0.62, 0.38])
        body_w = round(upper_net_w * 3696 / 5968) if ratios == [0.62, 0.38] else round(upper_net_w * ratios[0])
        body_region = _rect(inner["x"], content_y, body_w, upper_h)
        face_region = _rect(inner["x"] + body_w + major_gap, content_y, upper_net_w - body_w, upper_h)
        detail_region = _rect(inner["x"], content_y + upper_h + major_gap, inner["width"], detail_h)

    body_area = _rect(body_region["x"], body_region["y"] + section_h + section_gap, body_region["width"], body_region["height"] - section_h - section_gap)
    body_cells = [_cell(f"body_{view}", r, label_h, view_id=view) for view, r in zip(board["body_views"], _split(body_area, len(board["body_views"]), gap))]
    face_cells: list[dict] = []
    if board.get("face_views"):
        face_area = _rect(face_region["x"], face_region["y"] + section_h + section_gap, face_region["width"], face_region["height"] - section_h - section_gap)
        views = board["face_views"]
        if len(views) == 3:
            left_w = round((face_area["width"] - gap) * 0.60)
            right_w = face_area["width"] - left_w - gap
            upper_right_h = (face_area["height"] - gap) // 2
            totals = [_rect(face_area["x"], face_area["y"], left_w, face_area["height"]),
                      _rect(face_area["x"] + left_w + gap, face_area["y"], right_w, upper_right_h),
                      _rect(face_area["x"] + left_w + gap, face_area["y"] + upper_right_h + gap, right_w, face_area["height"] - upper_right_h - gap)]
        else:
            totals = _split(face_area, len(views), gap)
        face_cells = [_cell(f"face_{view}", r, label_h, view_id=view) for view, r in zip(views, totals)]
    detail_cells: list[dict] = []
    if board.get("detail_ids"):
        detail_area = _rect(detail_region["x"], detail_region["y"] + section_h + section_gap, detail_region["width"], detail_region["height"] - section_h - section_gap)
        detail_cells = [_cell(f"detail_{part}", r, label_h, part_id=part) for part, r in zip(board["detail_ids"], _split(detail_area, len(board["detail_ids"]), gap))]
    section_rects = {"body": _rect(body_region["x"], body_region["y"], body_region["width"], section_h),
                     "face": _rect(face_region["x"], face_region["y"], face_region["width"], section_h) if face_region["width"] else None}
    if detail_cells:
        groups = {"detail_facial": detail_cells[:2], "detail_style": detail_cells[2:-2], "detail_footwear": detail_cells[-2:]}
        for key, cells in groups.items():
            if cells:
                start, end = cells[0]["rect"], cells[-1]["rect"]
                section_rects[key] = _rect(start["x"], detail_region["y"], end["x"] + end["width"] - start["x"], section_h)
    return {"orientation": "landscape", "aspect_ratio": [16, 9], "canvas_size": [target_w, target_h],
            "outer_frame": {"width_px": frame, "color": board["outer_frame"]["color"]},
            "inner_background": board.get("inner_background", "#F4F5F6"), "title_rect": title, "footer_rect": footer,
            "region_rects": {"body": body_region, "face": face_region, "detail": detail_region},
            "section_title_rects": section_rects, "cell_rects": {"body": body_cells, "face": face_cells, "detail": detail_cells},
            "label_rects": [c["label_rect"] for c in body_cells + face_cells + detail_cells], "cell_labels": [],
            "source_asset_ids": [], "crop_rects": [], "fit_mode": {"body": "contain_bottom", "face": "contain", "detail": "contain"}}


def _section_titles(spec: dict, catalog: dict) -> dict[str, str]:
    board = spec["board"]
    count = len(board["body_views"])
    details = set(board.get("detail_ids", []))
    if any("headpiece" in item or item == "hair_bun" for item in details):
        style_key = "headwear_style"
    elif any(item in details for item in {"back_connection", "upper_body_connection", "waist_mount", "side_asymmetry", "material_interface", "shoulder_L_01", "hip_R_01"}):
        style_key = "equipment_style"
    else:
        style_key = "style"
    footwear_key = "feet" if {"feet_three_quarter", "feet_profile"}.intersection(details) else "footwear"
    return {"body": catalog["sections"]["body_three"] if count == 3 else catalog["sections"]["body_multi"],
            "face": catalog["sections"]["face"], "detail_facial": catalog["sections"]["facial"],
            "detail_style": catalog["sections"][style_key], "detail_footwear": catalog["sections"][footwear_key]}


def _cell_text(kind: str, asset_id: str, catalog: dict) -> str:
    namespace = "body_views" if kind == "body" else "face_views" if kind == "face" else "parts"
    if asset_id not in catalog[namespace]:
        raise ValueError(f"missing zh-CN label-catalog entry for {kind}:{asset_id}")
    return catalog[namespace][asset_id]


def _draw_centered(draw: ImageDraw.ImageDraw, rect: dict, text: str, font, fill) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    x = rect["x"] + (rect["width"] - (box[2] - box[0])) // 2
    y = rect["y"] + (rect["height"] - (box[3] - box[1])) // 2 - box[1]
    draw.text((x, y), text, fill=fill, font=font)


def compose(spec: dict, base: Path, output: Path, width: int | None = None) -> tuple[int, int]:
    tasks = [task for task in spec["view_tasks"] if task.get("status") == "succeeded" and task.get("qa_result") == "pass" and task.get("asset_path")]
    board = spec["board"]
    groups = {"body": [_task_for(tasks, "full_body", item) for item in board["body_views"]],
              "face": [_task_for(tasks, "face", item) for item in board.get("face_views", [])],
              "detail": [_task_for(tasks, "detail", item) for item in board.get("detail_ids", [])]}
    target_w, target_h = board.get("target_canvas", [6144, 3456])
    if width:
        target_w, target_h = width, round(width * 9 / 16)
    layout = _layout(spec, target_w, target_h)
    frame_color, inner_color = _hex_color(layout["outer_frame"]["color"]), _hex_color(layout["inner_background"])
    canvas = Image.new("RGB", (target_w, target_h), frame_color)
    draw = ImageDraw.Draw(canvas)
    frame = layout["outer_frame"]["width_px"]
    draw.rectangle((frame, frame, target_w - frame - 1, target_h - frame - 1), fill=inner_color)
    title_font, title_font_path = _font(max(14, _scaled(48, target_w)))
    section_font, section_font_path = _font(max(12, _scaled(40, target_w)))
    label_font, label_font_path = _font(max(10, _scaled(36, target_w)))
    labels_cfg, catalog = board["labels"], _catalog()
    title_color, label_color = _hex_color(labels_cfg["title_color"]), _hex_color(labels_cfg["label_color"])
    title_text = spec.get("display_name") or f"人物资产 · {spec['look_id']}"
    draw.text((layout["title_rect"]["x"] + _scaled(12, target_w), layout["title_rect"]["y"] + _scaled(12, target_w)), title_text, fill=title_color, font=title_font)
    layout["labels"] = [{"label_id": "board_title", "region_id": "board", "text": title_text, "role": "board_title", "bound_view_id": None, "bound_part_ids": [], "rect": layout["title_rect"], "font": title_font_path, "color": labels_cfg["title_color"], "alignment": "left"}]
    for name, text in _section_titles(spec, catalog).items():
        rect = layout["section_title_rects"].get(name)
        if rect:
            draw.text((rect["x"], rect["y"]), text, fill=title_color, font=section_font)
            layout["labels"].append({"label_id": f"section_{name}", "region_id": name, "text": text, "role": "section_title", "bound_view_id": None, "bound_part_ids": [], "rect": rect, "font": section_font_path, "color": labels_cfg["title_color"], "alignment": "left"})
    for kind, group in groups.items():
        for task, cell in zip(group, layout["cell_rects"][kind]):
            path = Path(task["asset_path"])
            path = path if path.is_absolute() else base / path
            with Image.open(path) as source:
                fitted = _fit(source, (cell["rect"]["width"], cell["rect"]["height"]), inner_color, "bottom" if kind == "body" else "center")
            canvas.paste(fitted, (cell["rect"]["x"], cell["rect"]["y"]))
            asset_id = task.get("detail_id") or task.get("view_id") or task["task_id"]
            text = _cell_text(kind, asset_id, catalog)
            _draw_centered(draw, cell["label_rect"], text, label_font, label_color)
            layout["source_asset_ids"].append(task["task_id"])
            layout["cell_labels"].append({"cell_id": cell["cell_id"], "text": text})
            layout["labels"].append({"label_id": f"label_{cell['cell_id']}", "cell_id": cell["cell_id"], "text": text, "role": "cell_label", "bound_view_id": cell.get("view_id"), "bound_part_ids": [cell["part_id"]] if cell.get("part_id") else [], "rect": cell["label_rect"], "font": label_font_path, "color": labels_cfg["label_color"], "alignment": "center"})
    footer_text = f"identity v{spec['identity_version']} · look v{spec['look_version']} · board v{spec['board_version']}"
    draw.text((layout["footer_rect"]["x"], layout["footer_rect"]["y"] + _scaled(8, target_w)), footer_text, fill=label_color, font=label_font)
    layout["labels"].append({"label_id": "footer_note", "region_id": "footer", "text": footer_text, "role": "footer_note", "bound_view_id": None, "bound_part_ids": [], "rect": layout["footer_rect"], "font": label_font_path, "color": labels_cfg["label_color"], "alignment": "left"})
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    output.with_suffix(".layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return canvas.size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int)
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
