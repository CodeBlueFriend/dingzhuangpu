from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mm_character_assets_import import compose_board, plan_board, validate_spec  # noqa: E402


def base_spec() -> dict:
    return {
        "schema_version": "1.0",
        "character_id": "char_test",
        "identity_version": 1,
        "look_id": "look_001",
        "look_version": 1,
        "condition_id": "neutral",
        "board_version": 1,
        "project_state": "spec_locked",
        "rendering_style": "photoreal",
        "spec_revision": 1,
        "reference_registry": [{
            "reference_id": "ref_face_001", "asset_path": "face.png", "role": ["identity"],
            "scope": ["face"], "source": "user", "limitations": []
        }],
        "part_coverage": [{
            "part_id": "shirt_01", "required_by": "user", "anatomical_side": "not_applicable",
            "attachment_location": "torso", "visible_in": ["front", "left_profile", "back"],
            "occluded_in": [], "coverage_cells": ["front", "left_profile", "back"],
            "detail_priority": "required", "reference_source": "design_completion", "qa_status": "pending"
        }],
        "view_tasks": [],
        "review_method": None,
        "user_approved": False,
        "inputs": {
            "identity_reference": "ref_face_001", "additional_references": [],
            "user_requirements": ["白衬衫"], "output_mode": "generate", "board_content": "asset_board"
        },
        "routing": {
            "genre": "modern", "genre_source": "user", "era": None,
            "profiles": ["modern-basic"], "inference_notes": []
        },
        "identity": {
            "reference_id": "ref_face_001", "features": [{"id": "face_shape", "description": "oval"}],
            "lock_status": "provisional", "input_quality": "usable"
        },
        "body": {"height_cm": None, "proportions": "natural", "source": "design_default"},
        "costume": {
            "layers": [{"id": "shirt_01", "description": "white shirt"}],
            "hair": {"id": "hair_01", "description": "short"}, "headwear": [], "accessories": [],
            "footwear": {"id": "shoe_01", "description": "black shoes"},
            "front_structure": {"description": "button placket"},
            "side_structure": {"description": "straight seam"},
            "back_structure": {"description": "plain yoke"}, "forbidden_additions": ["jewelry"]
        },
        "complexity": {
            "dimensions": {
                "clothing_layers": 0, "head_design": 0, "patterns_materials": 0,
                "accessories_props": 0, "side_asymmetry": 0, "occlusion_back": 0
            },
            "score": 0, "tier": "simple", "required_details": []
        },
        "board": {
            "mode": "auto", "layout_id": "simple_three_view", "body_views": [],
            "face_views": [], "detail_ids": [], "target_canvas": [4096, 3072], "actual_canvas": None
        },
        "generation": {
            "strategy": "anchor_then_views", "adapter": None, "anchor_asset_id": None,
            "budget": {"max_image_requests": 16, "max_total_repairs": 4, "max_repairs_per_unit": 2}, "calls": []
        },
        "qa": {"status": "pending", "checks": [], "unverified_items": []},
        "artifacts": []
    }


class PlanTests(unittest.TestCase):
    def test_auto_simple_uses_three_body_views(self):
        result = plan_board.plan(base_spec())
        self.assertEqual(result["board"]["body_views"], ["front", "left_profile", "back"])
        self.assertEqual(result["complexity"], {"score": 0, "tier": "simple"})
        self.assertEqual(result["board"]["detail_ids"], [], "a clearly covered shirt must not consume a detail cell")

    def test_complex_asymmetry_adds_real_right_side(self):
        spec = base_spec()
        spec["complexity"]["dimensions"] = {name: 2 for name in plan_board.DIMENSIONS}
        result = plan_board.plan(spec)
        self.assertEqual(result["board"]["body_views"][-1], "right_profile")
        self.assertEqual(len(result["board"]["body_views"]), 4)

    def test_explicit_three_view_is_never_expanded(self):
        spec = base_spec()
        spec["board"]["mode"] = "three_view"
        spec["board"]["body_views"] = ["front", "right_profile", "back"]
        spec["complexity"]["dimensions"] = {name: 2 for name in plan_board.DIMENSIONS}
        result = plan_board.plan(spec)
        self.assertEqual(result["board"]["body_views"], ["front", "right_profile", "back"])

    def test_body_only_removes_face_and_detail_cells(self):
        spec = base_spec()
        spec["board"]["mode"] = "three_view"
        spec["inputs"]["board_content"] = "body_only"
        result = plan_board.plan(spec)
        self.assertEqual(result["board"]["face_views"], [])
        self.assertEqual(result["board"]["detail_ids"], [])

    def test_budget_rejects_oversized_plan(self):
        spec = base_spec()
        spec["generation"]["budget"]["max_image_requests"] = 1
        with self.assertRaisesRegex(ValueError, "exceed budget"):
            plan_board.plan(spec)


class ValidateTests(unittest.TestCase):
    def test_published_example_specs_match_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((ROOT / "mm-character-assets/assets/character-spec.schema.json").read_text(encoding="utf-8"))
        for path in sorted((ROOT / "examples/specs").glob("*.json")):
            with self.subTest(spec=path.name):
                jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)

    def test_valid_locked_spec(self):
        self.assertEqual(validate_spec.validate(base_spec(), ROOT, check_files=False), [])

    def test_duplicate_parts_and_wrong_three_view_fail(self):
        spec = base_spec()
        spec["part_coverage"].append(copy.deepcopy(spec["part_coverage"][0]))
        spec["board"]["mode"] = "three_view"
        spec["board"]["body_views"] = ["front", "back"]
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("part_id" in error for error in errors))
        self.assertTrue(any("exactly 3" in error for error in errors))

    def test_unresolved_required_part_blocks_lock(self):
        spec = base_spec()
        spec["part_coverage"][0]["reference_source"] = "unresolved"
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("remain unresolved" in error for error in errors))

    def test_anchor_state_requires_visual_evidence(self):
        spec = base_spec()
        errors = validate_spec.validate(spec, ROOT, target_state="anchor_ready", check_files=False)
        self.assertTrue(any("verified_anchor" in error for error in errors))
        self.assertTrue(any("review_method" in error for error in errors))


class ComposeTests(unittest.TestCase):
    def test_composer_exports_requested_size_from_passed_assets(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            colors = {"front": "#d18c77", "left_profile": "#7895b2", "back": "#8e7aa8"}
            tasks = []
            for view, color in colors.items():
                path = root / f"{view}.png"
                Image.new("RGB", (320, 640), color).save(path)
                tasks.append({
                    "task_id": f"body_{view}", "spec_revision": 1, "view_id": view,
                    "framing": "full_body", "status": "succeeded", "asset_path": path.name,
                    "qa_result": "pass", "attempt_count": 1, "required": True
                })
            spec = base_spec()
            spec["board"]["body_views"] = list(colors)
            spec["view_tasks"] = tasks
            output = root / "board.png"
            size = compose_board.compose(spec, root, output, width=1024)
            self.assertEqual(size, (1024, 768))
            self.assertTrue(output.is_file())

    def test_composer_refuses_failed_required_view(self):
        spec = base_spec()
        spec["board"]["body_views"] = ["front"]
        spec["view_tasks"] = [{
            "task_id": "front", "view_id": "front", "framing": "full_body",
            "status": "failed", "qa_result": "fail", "asset_path": "front.png"
        }]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing passed"):
                compose_board.compose(spec, Path(directory), Path(directory) / "board.png")


if __name__ == "__main__":
    unittest.main()
