#!/usr/bin/env python3
"""Validate a 定妆谱 character spec, including stage-aware invariants."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

STAGE_ORDER = {
    "received": 0, "analyzed": 1, "spec_locked": 2, "anchor_ready": 3,
    "views_ready": 4, "assembled": 5, "delivered": 6,
}
TERMINAL_STATES = {"blocked", "needs_review", "draft_failed", "prompt_package_ready", "cancelled"}
VALID_VIEWS = {"front", "left_profile", "back", "right_profile", "left_three_quarter", "right_three_quarter"}


def _nonempty(value: object) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def validate(spec: dict, base: Path, target_state: str | None = None, check_files: bool = True) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version", "character_id", "identity_version", "look_id", "look_version",
        "condition_id", "board_version", "project_state", "rendering_style", "spec_revision",
        "reference_registry", "part_coverage", "view_tasks", "review_method", "user_approved",
        "inputs", "routing", "identity", "body", "costume", "complexity", "board", "generation", "qa", "artifacts",
    ]
    for key in required:
        if key not in spec:
            errors.append(f"missing required field: {key}")
    if errors:
        return errors

    state = target_state or spec["project_state"]
    if state not in STAGE_ORDER and state not in TERMINAL_STATES and state != "repairing":
        errors.append(f"invalid project_state: {state}")

    refs = spec["reference_registry"]
    ref_ids = [item.get("reference_id") for item in refs]
    if len(ref_ids) != len(set(ref_ids)):
        errors.append("reference_id values must be unique")
    identity_ref = spec["inputs"].get("identity_reference")
    if identity_ref not in ref_ids:
        errors.append("inputs.identity_reference must resolve in reference_registry")
    if spec["identity"].get("reference_id") != identity_ref:
        errors.append("identity.reference_id must equal inputs.identity_reference")
    if check_files:
        for item in refs:
            asset = item.get("asset_path")
            if asset and not _resolve(base, asset).is_file():
                errors.append(f"reference file is not readable: {asset}")

    parts = spec["part_coverage"]
    part_ids = [item.get("part_id") for item in parts]
    if len(part_ids) != len(set(part_ids)):
        errors.append("part_id values must be unique")

    board = spec["board"]
    body_views = board.get("body_views", [])
    if len(body_views) != len(set(body_views)):
        errors.append("board.body_views must not contain duplicates")
    unknown_views = sorted(set(body_views) - VALID_VIEWS)
    if unknown_views and board.get("mode") != "custom":
        errors.append(f"unknown non-custom body views: {', '.join(unknown_views)}")
    if board.get("mode") == "three_view" and len(body_views) != 3:
        errors.append("three_view mode requires exactly 3 body views")
    if spec["inputs"].get("board_content") == "body_only":
        if board.get("face_views") or board.get("detail_ids"):
            errors.append("body_only boards cannot contain face or detail cells")

    budget = spec["generation"].get("budget", {})
    for key in ("max_image_requests", "max_total_repairs", "max_repairs_per_unit"):
        value = budget.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"generation.budget.{key} must be a non-negative integer")
    if len(spec["generation"].get("calls", [])) > budget.get("max_image_requests", 0):
        errors.append("generation calls exceed max_image_requests")

    stage = STAGE_ORDER.get(state, -1)
    if stage >= STAGE_ORDER["analyzed"]:
        if spec["identity"].get("input_quality") == "missing_required":
            errors.append("missing_required identity input cannot enter analyzed state")
        if not _nonempty(spec["routing"].get("profiles")):
            errors.append("routing.profiles is required from analyzed state")

    if stage >= STAGE_ORDER["spec_locked"]:
        costume = spec["costume"]
        for key in ("layers", "hair", "footwear", "front_structure", "side_structure", "back_structure"):
            if not _nonempty(costume.get(key)):
                errors.append(f"costume.{key} is required for spec_locked")
        unresolved = [p.get("part_id") for p in parts if p.get("detail_priority") == "required" and p.get("reference_source") == "unresolved"]
        if unresolved:
            errors.append("required parts remain unresolved: " + ", ".join(unresolved))
        uncovered = [p.get("part_id") for p in parts if p.get("detail_priority") == "required" and not p.get("coverage_cells")]
        if uncovered:
            errors.append("required parts lack coverage cells: " + ", ".join(uncovered))
        planned = len(spec["view_tasks"])
        if planned > budget.get("max_image_requests", 0):
            errors.append("base view plan exceeds max_image_requests")

    tasks = spec["view_tasks"]
    task_ids = [t.get("task_id") for t in tasks]
    if len(task_ids) != len(set(task_ids)):
        errors.append("task_id values must be unique")
    if stage >= STAGE_ORDER["anchor_ready"]:
        if spec["identity"].get("lock_status") != "verified_anchor":
            errors.append("anchor_ready requires identity.lock_status=verified_anchor")
        if not spec["generation"].get("anchor_asset_id"):
            errors.append("anchor_ready requires generation.anchor_asset_id")
        if not spec.get("review_method"):
            errors.append("anchor_ready requires review_method")

    if stage >= STAGE_ORDER["views_ready"]:
        required_tasks = [t for t in tasks if t.get("required", True)]
        bad = [t.get("task_id") for t in required_tasks if t.get("status") != "succeeded" or t.get("qa_result") != "pass"]
        if bad:
            errors.append("required view tasks are not passed: " + ", ".join(bad))
        if check_files:
            for task in required_tasks:
                asset = task.get("asset_path")
                if not asset or not _resolve(base, asset).is_file():
                    errors.append(f"required task asset is not readable: {task.get('task_id')}")

    if stage >= STAGE_ORDER["assembled"]:
        board_assets = [a for a in spec["artifacts"] if a.get("type") == "board"]
        if not board_assets:
            errors.append("assembled requires a board artifact")
        elif check_files and not any(_resolve(base, a.get("path", "")).is_file() for a in board_assets):
            errors.append("assembled board artifact is not readable")
        actual = board.get("actual_canvas")
        if not isinstance(actual, list) or len(actual) != 2 or not all(isinstance(v, int) and v > 0 for v in actual):
            errors.append("assembled requires a positive two-value actual_canvas")

    if state == "delivered":
        if spec["qa"].get("status") != "pass":
            errors.append("delivered requires qa.status=pass")
        if spec["qa"].get("unverified_items"):
            errors.append("delivered cannot contain unverified_items")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--target-state", choices=list(STAGE_ORDER) + sorted(TERMINAL_STATES) + ["repairing"])
    parser.add_argument("--no-check-files", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read spec: {exc}", file=sys.stderr)
        return 2
    errors = validate(spec, args.spec.parent, args.target_state, not args.no_check_files)
    if args.as_json:
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
