#!/usr/bin/env python3
"""Plan body, face, and detail cells without overriding explicit requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DIMENSIONS = ("clothing_layers", "head_design", "patterns_materials", "accessories_props", "side_asymmetry", "occlusion_back")
CORE_DETAILS = ["eyes_brows", "nose_lips", "footwear_three_quarter", "footwear_profile"]
DETAIL_CATALOGUES = {
    "modern": ["hair_back", "neckline", "waist_or_hem", "cuff", "material_detail", "lower_garment_structure"],
    "historical": ["hair_back", "neckline_layers", "sleeve_structure", "waist_structure", "main_pattern", "hem_structure"],
    "special": ["back_connection", "upper_body_connection", "waist_mount", "glove_or_cuff", "side_asymmetry", "material_interface"],
}


def tier_for(score: int) -> str:
    if score <= 3:
        return "simple"
    if score <= 7:
        return "medium"
    return "complex"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _frame_width(height: int) -> int:
    return max(8, int((height * 0.02 + 4) // 8 * 8))


def _profile_family(spec: dict) -> str:
    text = " ".join([spec.get("routing", {}).get("genre", ""), *spec.get("routing", {}).get("profiles", [])]).lower()
    if any(token in text for token in ("histor", "ancient", "period", "古装", "年代")):
        return "historical"
    if any(token in text for token in ("scifi", "science", "tactical", "fantasy", "uniform", "科幻", "战术", "制服", "奇幻")):
        return "special"
    return "modern"


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

    required_details = _dedupe(spec["complexity"].get("required_details", []))
    required_parts = [
        part["part_id"] for part in spec.get("part_coverage", [])
        if part.get("detail_priority") == "required"
        and not set(part.get("coverage_cells", [])).intersection(body_views)
        and part["part_id"] not in required_details
    ]
    required_details.extend(required_parts)

    detail_level = board.get("detail_level", "enhanced")
    if detail_level not in {"enhanced", "compact"}:
        raise ValueError("board.detail_level must be enhanced or compact")

    if content == "body_only":
        face_views: list[str] = []
        detail_ids: list[str] = []
        required_detail_categories: list[str] = []
        layout_id = "landscape_body_only"
        canvas = [4096, 2304]
    elif detail_level == "compact":
        face_views = list(board.get("face_views") or ["front", "left_three_quarter"])
        detail_ids = _dedupe(required_details + required_parts)[:2]
        required_detail_categories = []
        layout_id = "landscape_compact_three_view"
        canvas = [4096, 2304]
    else:
        face_views = list(board.get("face_views") or ["front", "left_three_quarter", "left_profile"])
        family_details = DETAIL_CATALOGUES[_profile_family(spec)]
        detail_ids = _dedupe(CORE_DETAILS + required_details + required_parts + family_details)
        target_count = 10 if tier == "complex" or len(body_views) >= 4 else 8
        # Required and core details are never truncated. Optional catalogue entries fill capacity only.
        if len(detail_ids) > target_count:
            mandatory = set(CORE_DETAILS + required_details + required_parts)
            detail_ids = [item for item in detail_ids if item in mandatory] + [item for item in detail_ids if item not in mandatory][:max(0, target_count - len(mandatory))]
            detail_ids = _dedupe(detail_ids)
        required_detail_categories = ["eyes_brows", "nose_lips", "footwear_or_feet"]
        if tier == "complex" or len(body_views) >= 4:
            layout_id = "landscape_enhanced_complex"
            canvas = [7680, 4320]
        else:
            layout_id = "landscape_enhanced_three_view"
            canvas = [6144, 3456]

    frame = _frame_width(canvas[1])
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
            "detail_level": detail_level,
            "orientation": "landscape",
            "aspect_ratio": [16, 9],
            "outer_frame": {"enabled": True, "color": "#FFFFFF", "width_px": frame},
            "inner_background": "#F4F5F6",
            "region_width_ratios": [0.46, 0.24, 0.30],
            "required_detail_categories": required_detail_categories,
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
