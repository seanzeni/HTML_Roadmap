"""Validate roadmap configuration and generate one self-contained HTML file."""

from __future__ import annotations

import argparse
import getpass
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates" / "roadmap_template.html"
CSS = ROOT / "static" / "roadmap.css"
JS = ROOT / "static" / "roadmap.js"
PDF_LIBRARY = ROOT / "static" / "vendor" / "pdf-lib.min.js"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def require_id(value: Any, location: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(f"{location} must use lowercase letters, numbers, hyphens, or underscores and start with a letter")
    return value


def load_configuration(config_dir: Path) -> dict:
    settings = read_json(config_dir / "settings.json")
    categories_doc = read_json(config_dir / "categories.json")
    filters_doc = read_json(config_dir / "filters.json")
    lane_dir = config_dir / settings.get("lanes_directory", "lanes")
    lane_files = sorted(lane_dir.glob("*.json"))
    if not lane_files:
        raise ValueError(f"No swim-lane JSON files found in {lane_dir}")
    lanes = [read_json(path) | {"_source": path.name} for path in lane_files]
    return {"settings": settings, "categories": categories_doc, "filters": filters_doc, "lanes": lanes}


def validate(configuration: dict) -> dict:
    settings = configuration["settings"]
    categories_doc = configuration["categories"]
    filters_doc = configuration["filters"]
    lanes = configuration["lanes"]
    errors: list[str] = []

    start_year = settings.get("start_year")
    end_year = settings.get("end_year")
    if not isinstance(start_year, int) or not isinstance(end_year, int) or end_year < start_year:
        errors.append("settings.json: start_year and end_year must be whole years, with end_year at or after start_year")
    default_rows = settings.get("rows_per_swim_lane")
    if not isinstance(default_rows, int) or default_rows < 1:
        errors.append("settings.json: rows_per_swim_lane must be a whole number of 1 or greater")

    categories = categories_doc.get("categories", [])
    category_ids: set[str] = set()
    if len(categories) > 10:
        errors.append(f"categories.json: at most 10 categories are allowed; found {len(categories)}")
    for index, category in enumerate(categories, 1):
        try:
            category_id = require_id(category.get("id"), f"categories.json category {index} id")
            if category_id in category_ids:
                errors.append(f"categories.json: duplicate category id '{category_id}'")
            category_ids.add(category_id)
        except ValueError as exc:
            errors.append(str(exc))
        if not category.get("label"):
            errors.append(f"categories.json: category {index} needs a label")

    schemes = settings.get("color_schemes", {})
    selected_scheme = settings.get("color_scheme")
    if selected_scheme not in schemes:
        errors.append(f"settings.json: color_scheme '{selected_scheme}' is not defined in color_schemes")
    required_ui_colors = {"background", "foreground", "muted", "line", "panel", "sub_lane", "bar_text"}
    for scheme_id, scheme in schemes.items():
        missing_ui = required_ui_colors - set(scheme.get("ui", {}))
        palette = scheme.get("category_palette", [])
        if missing_ui:
            errors.append(f"settings.json: scheme '{scheme_id}' is missing UI colors: {', '.join(sorted(missing_ui))}")
        if not isinstance(palette, list):
            errors.append(f"settings.json: scheme '{scheme_id}' category_palette must be a list")
        elif len(palette) < len(categories):
            errors.append(f"settings.json: scheme '{scheme_id}' needs at least {len(categories)} palette colors; found {len(palette)}")
        elif len(palette) > 10:
            errors.append(f"settings.json: scheme '{scheme_id}' category_palette may contain at most 10 colors")

    filter_groups = filters_doc.get("filters", [])
    filter_values: dict[str, set[str]] = {}
    defaults: dict[str, str] = {}
    for index, group in enumerate(filter_groups, 1):
        try:
            group_id = require_id(group.get("id"), f"filters.json filter {index} id")
        except ValueError as exc:
            errors.append(str(exc)); continue
        if group_id in filter_values:
            errors.append(f"filters.json: duplicate filter id '{group_id}'")
        values = {str(option.get("value")) for option in group.get("options", [])}
        if not values:
            errors.append(f"filters.json: filter '{group_id}' needs at least one option")
        if group.get("default") not in values:
            errors.append(f"filters.json: default for '{group_id}' must match an option value")
        filter_values[group_id] = values
        defaults[group_id] = group.get("default")

    lane_by_id: dict[str, dict] = {}
    entry_ids: set[str] = set()
    for lane in lanes:
        source = lane.pop("_source")
        try:
            lane_id = require_id(lane.get("id"), f"{source}: lane id")
        except ValueError as exc:
            errors.append(str(exc)); continue
        if lane_id in lane_by_id:
            errors.append(f"{source}: duplicate lane id '{lane_id}'")
        lane_by_id[lane_id] = lane
        if not lane.get("label"):
            errors.append(f"{source}: lane needs a label")
        row_limit = lane.get("rows", default_rows)
        if not isinstance(row_limit, int) or row_limit < 1:
            errors.append(f"{source}: rows must be a whole number of 1 or greater")
            row_limit = 1
        lane["rows"] = row_limit
        for index, entry in enumerate(lane.get("entries", []), 1):
            prefix = f"{source} entry {index}"
            try:
                entry_id = require_id(entry.get("id"), f"{prefix} id")
                if entry_id in entry_ids:
                    errors.append(f"{prefix}: duplicate entry id '{entry_id}'")
                entry_ids.add(entry_id)
            except ValueError as exc:
                errors.append(str(exc))
            row = entry.get("row", 1)
            if not isinstance(row, int) or row < 1 or row > row_limit:
                errors.append(f"{prefix}: row {row!r} is outside the allowed range 1–{row_limit}")
            if entry.get("category") not in category_ids:
                errors.append(f"{prefix}: unknown category '{entry.get('category')}'")
            if "point" not in entry and not {"start", "end"} <= entry.keys():
                errors.append(f"{prefix}: provide point, or both start and end")
            if "point" in entry and ("start" in entry or "end" in entry):
                errors.append(f"{prefix}: use point or start/end, not both")
            for filter_id, value in entry.get("when", {}).items():
                if filter_id not in filter_values:
                    errors.append(f"{prefix}: unknown filter criterion '{filter_id}'")
                elif value not in filter_values[filter_id]:
                    errors.append(f"{prefix}: invalid value '{value}' for filter '{filter_id}'")

    lane_order = settings.get("lane_order", [])
    unknown_order = set(lane_order) - set(lane_by_id)
    unordered = set(lane_by_id) - set(lane_order)
    if unknown_order:
        errors.append(f"settings.json: lane_order contains unknown lanes: {', '.join(sorted(unknown_order))}")
    if unordered:
        errors.append(f"settings.json: lane_order is missing lanes: {', '.join(sorted(unordered))}")
    if len(lane_order) != len(set(lane_order)):
        errors.append("settings.json: lane_order contains duplicates")

    if errors:
        raise ValueError("Configuration validation failed:\n- " + "\n- ".join(errors))

    ordered_lanes = [lane_by_id[lane_id] for lane_id in lane_order]
    entries = []
    for lane in ordered_lanes:
        for entry in lane.get("entries", []):
            entries.append(entry | {"lane": lane["id"], "row": entry.get("row", 1) - 1})
    warnings = find_overlap_warnings(entries, ordered_lanes)
    selected_theme = schemes[selected_scheme]
    category_colors = {
        category["id"]: selected_theme["category_palette"][index]
        for index, category in enumerate(categories)
    }
    return {
        "title": settings["title"], "subtitle": settings.get("subtitle", ""),
        "start_year": start_year, "end_year": end_year,
        "lanes": [{k: v for k, v in lane.items() if k != "entries"} for lane in ordered_lanes],
        "entries": entries, "categories": categories,
        "scenario_groups": filter_groups, "filter_defaults": defaults,
        "theme": {"ui": selected_theme["ui"], "categories": category_colors},
        "theme_name": selected_scheme,
        "warnings": warnings,
    }


def find_overlap_warnings(entries: list[dict], lanes: list[dict]) -> list[str]:
    """Return same-row time conflicts that can appear in the same filter state."""
    lane_labels = {lane["id"]: lane["label"] for lane in lanes}
    warnings: list[str] = []

    def criteria_can_coexist(first: dict, second: dict) -> bool:
        shared = set(first.get("when", {})) & set(second.get("when", {}))
        return all(first["when"][key] == second["when"][key] for key in shared)

    def time_overlaps(first: dict, second: dict) -> bool:
        first_point, second_point = first.get("point"), second.get("point")
        if first_point is not None and second_point is not None:
            return first_point == second_point
        if first_point is not None:
            return second["start"] <= first_point < second["end"]
        if second_point is not None:
            return first["start"] <= second_point < first["end"]
        return max(first["start"], second["start"]) < min(first["end"], second["end"])

    for index, first in enumerate(entries):
        for second in entries[index + 1:]:
            if first["lane"] != second["lane"] or first["row"] != second["row"]:
                continue
            if criteria_can_coexist(first, second) and time_overlaps(first, second):
                warnings.append(
                    f"Overlap in {lane_labels[first['lane']]} row {first['row'] + 1}: "
                    f"'{first['id']}' and '{second['id']}' can be active at the same time"
                )
    return warnings


def generate_html(data: dict, destination: Path) -> None:
    replacements = {
        "__TITLE__": data["title"], "__CSS__": CSS.read_text(encoding="utf-8"),
        "__DATA__": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "__PDF_LIBRARY__": PDF_LIBRARY.read_text(encoding="utf-8"),
        "__JAVASCRIPT__": JS.read_text(encoding="utf-8"),
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    for placeholder, content in replacements.items():
        html = html.replace(placeholder, content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    print(f"Created HTML: {destination.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate configuration and generate a swimlane roadmap.")
    parser.add_argument(
        "config_dir",
        nargs="?",
        type=Path,
        default=ROOT / "config",
        help="Configuration folder (default: the config folder beside this script)",
    )
    parser.add_argument(
        "--generated-by",
        help="Name displayed in the generated HTML and PDF (default: current operating-system user)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.cwd() / "roadmap.html",
        help="Output HTML path or filename (default: roadmap.html in the current directory)",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        help="PDF output path (default: same name and folder as the HTML output)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate all configuration files without creating HTML or PDF output",
    )
    args = parser.parse_args()
    output = args.output if args.output.suffix else args.output.with_suffix(".html")
    try:
        data = validate(load_configuration(args.config_dir.resolve()))
        print("Configuration validation passed.")
        for warning in data["warnings"]:
            print(f"WARNING: {warning}")
        if args.validate_only:
            return
        data["generated_at"] = datetime.now().astimezone().strftime("%Y-%m-%d %I:%M %p %Z")
        data["generated_by"] = args.generated_by or getpass.getuser()
        html_output = output.resolve()
        pdf_output = (args.pdf_output or html_output.with_suffix(".pdf")).resolve()
        generate_html(data, html_output)
        from pdf_exporter import export_pdf
        export_pdf(data, pdf_output)
        print(f"Created PDF:  {pdf_output}")
    except ValueError as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
