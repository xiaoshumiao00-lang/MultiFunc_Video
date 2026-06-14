#!/usr/bin/env python3
"""Convert ComfyUI workflow from UI format to API format."""

import json
from pathlib import Path
from typing import Any


def convert_ui_to_api(ui_workflow: dict[str, Any]) -> dict[str, Any]:
    """Convert a ComfyUI UI-format workflow to API format."""
    nodes = ui_workflow.get("nodes", [])
    links = ui_workflow.get("links", [])

    # Build link lookup: target_node_id -> target_slot_index -> [source_node_id, source_slot_index]
    incoming: dict[int, dict[int, list[int]]] = {}
    for link in links:
        # link format: [id, origin_id, origin_slot, target_id, target_slot, type]
        if len(link) < 6:
            continue
        _, origin_id, origin_slot, target_id, target_slot, _ = link
        incoming.setdefault(target_id, {})[target_slot] = [str(origin_id), origin_slot]

    api_workflow: dict[str, Any] = {}

    for node in nodes:
        node_id = node["id"]
        node_type = node.get("type", "")
        inputs_list = node.get("inputs", [])
        outputs_list = node.get("outputs", [])
        widgets_values = node.get("widgets_values", [])
        title = node.get("title") or node.get("properties", {}).get("Node name for S&R") or node_type

        # Build widget value lookup
        widget_inputs = [inp for inp in inputs_list if "widget" in inp]
        widget_values: dict[str, Any] = {}

        if isinstance(widgets_values, dict):
            # dict form: keys are input/widget names
            widget_values = dict(widgets_values)
        elif isinstance(widgets_values, list):
            # list form: values in order of widget inputs
            for idx, inp in enumerate(widget_inputs):
                if idx < len(widgets_values):
                    widget_values[inp["name"]] = widgets_values[idx]

        # Build inputs dict
        inputs: dict[str, Any] = {}
        for slot_idx, inp in enumerate(inputs_list):
            name = inp.get("name")
            if not name:
                continue

            # 1. If connected, use link source
            if "link" in inp and inp["link"] is not None:
                src = incoming.get(node_id, {}).get(slot_idx)
                if src:
                    inputs[name] = src
                continue

            # 2. If it's a widget input without link, use widget value
            if "widget" in inp:
                if name in widget_values:
                    inputs[name] = widget_values[name]
                continue

            # 3. Otherwise leave unset

        api_node: dict[str, Any] = {
            "inputs": inputs,
            "class_type": node_type,
            "_meta": {"title": title},
        }

        api_workflow[str(node_id)] = api_node

    return api_workflow


def convert_file(ui_path: Path, api_path: Path):
    workflow = json.loads(ui_path.read_text(encoding="utf-8"))
    if isinstance(workflow, dict) and any(isinstance(v, dict) and "class_type" in v for v in workflow.values()):
        print(f"Skip (already API format): {ui_path}")
        return
    if not (isinstance(workflow, dict) and "nodes" in workflow and "links" in workflow):
        print(f"Skip (unrecognized format): {ui_path}")
        return
    api_workflow = convert_ui_to_api(workflow)
    api_path.write_text(json.dumps(api_workflow, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Converted workflow saved to: {api_path}")


def main():
    files = [
        Path("D:/陈潘HBEU/Desktop/Pixelle-Video-v0.1.15-win64/Pixelle-Video/workflows/selfhost/digital_combination.json"),
        Path("D:/陈潘HBEU/Desktop/Pixelle-Video-v0.1.15-win64/output/digital_combination_optimized_16gb.json"),
        Path("D:/陈潘HBEU/Desktop/Pixelle-Video-v0.1.15-win64/output/digital_combination_lite_no_multitalk.json"),
    ]
    for ui_path in files:
        if not ui_path.exists():
            print(f"Skip (not found): {ui_path}")
            continue
        api_path = ui_path.with_suffix(".api.json")
        convert_file(ui_path, api_path)


if __name__ == "__main__":
    main()
