#!/usr/bin/env python3
"""Plan body, face, and detail cells without overriding explicit requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DIMENSIONS = ("clothing_layers", "head_design", "patterns_materials", "accessories_props", "side_asymmetry", "occlusion_back")


def tier_for(score: int) -> str:
    if score <= 3:
        return "simple"
    if score <= 7:
        return "medium"
    return "complex"


def plan(spec: dict) -> dict:
    board = spec["board"]
    inputs = spec["inputs"]
    dims = spec["complexity"].get("dimensions", {})
    missing = [name for name in DIMENSIONS if name not in dims]
    if missing:
        raise ValueError("missing complexity dimensions: " + ", ".join(missing))
    invalid = [name for name, value in dims.items() if name in DIMENSIONS and value not in (0, 1, 2)]
    if invalid:
        raise ValueError("complexity values must be 0, 1, or 2: " + ", ".join(invalid))
    score = sum(dims[name] for name in DIMENSIONS)
    tier = tier_for(score)
    mode = board.get("mode", "auto")
    content = inputs.get("board_content", "asset_board")

    requested = list(board.get("body_views") or [])
    if mode == "three_view":
        body_views = requested or ["front", "left_profile", "back"]
        if len(body_views) != 3:
            raise ValueError("three_view mode requires exactly 3 requested body views")
    elif mode == "custom":
        if not requested:
            raise ValueError("custom mode requires explicit body_views")
        body_views = requested
    elif mode == "multiview":
        body_views = requested or ["front", "left_profile", "back", "right_profile"]
    else:
        body_views = ["front", "left_profile", "back"]
        if tier == "complex":
            fourth = "right_profile" if dims["side_asymmetry"] > 0 else "left_three_quarter"
            body_views.append(fourth)

    if len(body_views) != len(set(body_views)):
        raise ValueError("body_views contains duplicates")

    required_details = list(dict.fromkeys(spec["complexity"].get("required_details", [])))
    required_parts = [
        part["part_id"] for part in spec.get("part_coverage", [])
        if part.get("detail_priority") == "required"
        and not set(part.get("coverage_cells", [])).intersection(body_views)
        and part["part_id"] not in required_details
    ]
    required_details.extend(required_parts)

    if content == "body_only":
        face_views: list[str] = []
        detail_ids: list[str] = []
        layout_id = "body_only_three_view" if len(body_views) == 3 else "complex_asset_board"
    else:
        face_views = list(board.get("face_views") or (["front", "left_three_quarter"] if tier == "simple" else ["front", "left_three_quarter", "left_profile"]))
        max_details = 1 if tier == "simple" else 3 if tier == "medium" else 4
        detail_ids = required_details[:max_details]
        if tier == "simple" and len(body_views) == 3:
            layout_id = "simple_three_view"
        elif tier == "complex" or len(body_views) >= 4:
            layout_id = "complex_asset_board"
        else:
            layout_id = "standard_asset_board"

    canvas = [6144, 4096] if layout_id == "complex_asset_board" else [4096, 3072]
    base_requests = len(body_views) + len(face_views) + len(detail_ids)
    if "front" in body_views:
        base_requests -= 1  # 正面全身基准同时作为主视图
    base_requests += 1
    budget = spec["generation"]["budget"]["max_image_requests"]
    if base_requests > budget:
        raise ValueError(f"planned base requests {base_requests} exceed budget {budget}")

    return {
        "complexity": {"score": score, "tier": tier},
        "board": {
            "mode": mode,
            "layout_id": layout_id,
            "body_views": body_views,
            "face_views": face_views,
            "detail_ids": detail_ids,
            "target_canvas": canvas,
        },
        "budget": {"base_image_requests": base_requests, "max_image_requests": budget, "remaining_for_repairs": budget - base_requests},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--write", action="store_true", help="write the plan back into the input spec")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        result = plan(spec)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"planning failed: {exc}", file=sys.stderr)
        return 1
    if args.write:
        spec["complexity"].update(result["complexity"])
        spec["board"].update(result["board"])
        args.spec.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
