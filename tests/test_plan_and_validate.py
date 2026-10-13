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
        "schema_version": "1.2",
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
            "mode": "auto", "layout_id": "landscape_top_views_bottom_details", "detail_level": "enhanced",
            "orientation": "landscape", "aspect_ratio": [16, 9],
            "outer_frame": {"enabled": True, "color": "#FFFFFF", "width_px": 72},
            "inner_background": "#F4F5F6", "upper_region_width_ratios": [0.62, 0.38],
            "content_height_ratios": [0.685, 0.315], "detail_placement": "bottom",
            "labels": {"enabled": True, "language": "zh-CN", "section_titles_enabled": True,
                       "per_cell_labels_enabled": True, "position": "outside_image",
                       "cell_label_height_px": 48, "title_color": "#30343B", "label_color": "#4B515B"},
            "required_detail_categories": ["eyes_brows", "nose_lips", "footwear_or_feet"],
            "body_views": ["front", "left_profile", "back"],
            "face_views": ["front", "left_three_quarter", "left_profile"],
            "detail_ids": ["eyes_brows", "nose_lips", "hair_back", "neckline", "waist_or_hem", "cuff", "footwear_three_quarter", "footwear_profile"],
            "target_canvas": [6144, 3456], "actual_canvas": None
        },
        "generation": {
            "strategy": "anchor_then_views", "adapter": None, "anchor_asset_id": None,
            "budget": {"max_image_requests": 24, "max_total_repairs": 6, "max_repairs_per_unit": 2}, "calls": []
        },
        "qa": {"status": "pending", "checks": [], "unverified_items": []},
        "artifacts": []
    }


class PlanTests(unittest.TestCase):
    def test_auto_simple_uses_three_body_views(self):
        result = plan_board.plan(base_spec())
        self.assertEqual(result["board"]["body_views"], ["front", "left_profile", "back"])
        self.assertEqual(result["complexity"], {"score": 0, "tier": "simple"})
        self.assertEqual(result["board"]["layout_id"], "landscape_top_views_bottom_details")
        self.assertEqual(result["board"]["detail_placement"], "bottom")
        self.assertEqual(result["board"]["labels"]["language"], "zh-CN")
        self.assertEqual(result["board"]["target_canvas"], [6144, 3456])
        self.assertEqual(result["board"]["face_views"], ["front", "left_three_quarter", "left_profile"])
        self.assertEqual(len(result["board"]["detail_ids"]), 8)
        self.assertTrue(set(plan_board.CORE_DETAILS).issubset(result["board"]["detail_ids"]))
        self.assertEqual(result["board"]["detail_ids"][:2], plan_board.FACIAL_DETAILS)
        self.assertEqual(result["board"]["detail_ids"][-2:], plan_board.FOOTWEAR_DETAILS)
        self.assertEqual(result["budget"]["base_image_requests"], 14)

    def test_complex_asymmetry_adds_real_right_side(self):
        spec = base_spec()
        spec["complexity"]["dimensions"] = {name: 2 for name in plan_board.DIMENSIONS}
        result = plan_board.plan(spec)
        self.assertEqual(result["board"]["body_views"][-1], "right_profile")
        self.assertEqual(len(result["board"]["body_views"]), 4)
        self.assertEqual(result["board"]["target_canvas"], [7680, 4320])
        self.assertEqual(len(result["board"]["detail_ids"]), 10)
        self.assertEqual(result["budget"]["base_image_requests"], 17)

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
        self.assertEqual(result["board"]["layout_id"], "landscape_top_views_body_only")
        self.assertEqual(result["board"]["target_canvas"], [4096, 2304])

    def test_compact_requires_explicit_detail_level_and_keeps_landscape_frame(self):
        spec = base_spec()
        spec["board"]["detail_level"] = "compact"
        spec["board"]["face_views"] = []
        spec["board"]["detail_ids"] = []
        result = plan_board.plan(spec)
        self.assertEqual(result["board"]["layout_id"], "landscape_top_views_bottom_details_compact")
        self.assertEqual(result["board"]["face_views"], ["front", "left_three_quarter"])
        self.assertEqual(result["board"]["outer_frame"]["width_px"], 48)

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

    def test_enhanced_board_cannot_silently_drop_core_details(self):
        spec = base_spec()
        spec["board"]["detail_ids"].remove("nose_lips")
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("lacks core details" in error for error in errors))

    def test_v13_rejects_detail_order_that_breaks_group_titles(self):
        spec = base_spec()
        spec["board"]["detail_ids"] = ["eyes_brows", "nose_lips", "footwear_three_quarter", "footwear_profile", "hair_back", "neckline", "waist_or_hem", "cuff"]
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("detail order" in error for error in errors))

    def test_wrong_frame_width_and_portrait_canvas_fail(self):
        spec = base_spec()
        spec["board"]["target_canvas"] = [3456, 6144]
        spec["board"]["outer_frame"]["width_px"] = 1
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("landscape 16:9" in error for error in errors))
        self.assertTrue(any("rounded to 8px" in error for error in errors))

    def test_v13_rejects_missing_chinese_label_contract(self):
        spec = base_spec()
        spec["board"]["labels"]["position"] = "overlay"
        spec["board"]["detail_placement"] = "right"
        errors = validate_spec.validate(spec, ROOT, check_files=False)
        self.assertTrue(any("detail_placement" in error for error in errors))
        self.assertTrue(any("labels.position" in error for error in errors))

    def test_white_edge_inspection_distinguishes_valid_frame(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        with tempfile.TemporaryDirectory() as directory:
            white = Path(directory) / "white.png"
            dark = Path(directory) / "dark.png"
            Image.new("RGB", (160, 90), "white").save(white)
            Image.new("RGB", (160, 90), "#F4F5F6").save(dark)
            self.assertTrue(validate_spec._has_white_edges(white))
            self.assertFalse(validate_spec._has_white_edges(dark))

    def test_anchor_state_requires_visual_evidence(self):
        spec = base_spec()
        errors = validate_spec.validate(spec, ROOT, target_state="anchor_ready", check_files=False)
        self.assertTrue(any("verified_anchor" in error for error in errors))
        self.assertTrue(any("review_method" in error for error in errors))


class ComposeTests(unittest.TestCase):
    def test_reference_geometry_matches_v13_contract(self):
        layout = compose_board._layout(base_spec(), 6144, 3456)
        self.assertEqual(layout["outer_frame"]["width_px"], 72)
        self.assertEqual(layout["title_rect"], {"x": 72, "y": 72, "width": 6000, "height": 96})
        self.assertEqual(layout["footer_rect"], {"x": 72, "y": 3320, "width": 6000, "height": 64})
        self.assertEqual(layout["region_rects"]["body"], {"x": 72, "y": 192, "width": 3696, "height": 2104})
        self.assertEqual(layout["region_rects"]["face"], {"x": 3800, "y": 192, "width": 2272, "height": 2104})
        self.assertEqual(layout["region_rects"]["detail"], {"x": 72, "y": 2328, "width": 6000, "height": 968})
        self.assertEqual(layout["section_title_rects"]["detail_facial"]["width"], 1482)
        self.assertEqual(layout["section_title_rects"]["detail_style"]["width"], 2988)
        self.assertEqual(layout["section_title_rects"]["detail_footwear"]["width"], 1482)

    def test_chinese_label_catalog_keeps_character_side_mapping(self):
        catalog = json.loads((ROOT / "mm-character-assets/assets/label-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["body_views"]["left_profile"], "全身左侧")
        self.assertEqual(catalog["face_views"]["right_profile"], "右侧面部")
        self.assertEqual(catalog["parts"]["footwear_profile"], "鞋履侧面")

    def test_unknown_part_cannot_fall_back_to_raw_id(self):
        catalog = json.loads((ROOT / "mm-character-assets/assets/label-catalog.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "missing zh-CN"):
            compose_board._cell_text("detail", "unknown_custom_part", catalog)

    def test_body_only_keeps_section_and_cell_label_regions(self):
        spec = base_spec()
        spec["inputs"]["board_content"] = "body_only"
        spec["board"]["face_views"] = []
        spec["board"]["detail_ids"] = []
        layout = compose_board._layout(spec, 4096, 2304)
        self.assertIsNotNone(layout["section_title_rects"]["body"])
        self.assertEqual(len(layout["cell_rects"]["body"]), 3)
        self.assertTrue(all(cell["label_rect"]["height"] > 0 for cell in layout["cell_rects"]["body"]))
        self.assertEqual(layout["cell_rects"]["face"], [])
        self.assertEqual(layout["cell_rects"]["detail"], [])

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
            for view in spec["board"]["face_views"]:
                path = root / f"face-{view}.png"
                Image.new("RGB", (320, 320), "#d8b39b").save(path)
                tasks.append({
                    "task_id": f"face_{view}", "spec_revision": 1, "view_id": view,
                    "framing": "face", "status": "succeeded", "asset_path": path.name,
                    "qa_result": "pass", "attempt_count": 1, "required": True
                })
            for detail_id in spec["board"]["detail_ids"]:
                path = root / f"detail-{detail_id}.png"
                Image.new("RGB", (240, 180), "#b7a88f").save(path)
                tasks.append({
                    "task_id": f"detail_{detail_id}", "spec_revision": 1, "view_id": detail_id,
                    "detail_id": detail_id, "framing": "detail", "status": "succeeded", "asset_path": path.name,
                    "qa_result": "pass", "attempt_count": 1, "required": True
                })
            spec["board"]["body_views"] = list(colors)
            spec["view_tasks"] = tasks
            output = root / "board.png"
            size = compose_board.compose(spec, root, output, width=1024)
            self.assertEqual(size, (1024, 576))
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".layout.json").is_file())
            with Image.open(output) as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
                self.assertEqual(image.getpixel((1023, 575)), (255, 255, 255))
            layout = json.loads(output.with_suffix(".layout.json").read_text(encoding="utf-8"))
            self.assertEqual(layout["orientation"], "landscape")
            self.assertEqual(layout["aspect_ratio"], [16, 9])
            self.assertEqual(len(layout["cell_rects"]["detail"]), 8)
            self.assertEqual(len(layout["cell_labels"]), 14)
            self.assertTrue(all(item["role"] in {"board_title", "section_title", "cell_label", "footer_note"} for item in layout["labels"]))
            image_rects = {cell["cell_id"]: cell["rect"] for group in layout["cell_rects"].values() for cell in group}
            for label in (item for item in layout["labels"] if item["role"] == "cell_label"):
                image_rect = image_rects[label["cell_id"]]
                self.assertGreaterEqual(label["rect"]["y"], image_rect["y"] + image_rect["height"])
            for group in layout["cell_rects"].values():
                for cell in group:
                    rect = cell["rect"]
                    self.assertLessEqual(rect["x"] + rect["width"], 1024 - layout["outer_frame"]["width_px"])
                    self.assertLessEqual(cell["label_rect"]["y"] + cell["label_rect"]["height"], 576 - layout["outer_frame"]["width_px"])

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
