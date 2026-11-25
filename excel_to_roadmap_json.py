"""Convert the manager Excel intake workbook into roadmap JSON configuration files."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError as exc:  # pragma: no cover - friendly CLI dependency message
    raise SystemExit("openpyxl is required. Install it with: python -m pip install openpyxl") from exc


ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
REQUIRED_SHEETS = {"Settings", "Categories", "Filters", "Lanes", "Work Items", "Entry Filters"}


def clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "y", "1"}


def rows_by_header(sheet, header_row=6):
    headers = [clean(cell.value) for cell in sheet[header_row]]
    if not any(headers):
        raise ValueError(f"{sheet.title}: header row {header_row} is empty")
    for values in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        row = {header: clean(value) for header, value in zip(headers, values) if header}
        if any(value is not None for value in row.values()):
            yield row


def require_id(value, context, errors):
    value = str(value or "")
    if not ID_PATTERN.fullmatch(value):
        errors.append(f"{context}: '{value}' must begin with a lowercase letter and use only lowercase letters, numbers, _ or -")
    return value


def numeric(value, context, errors, integer=False):
    if value is None:
        return None
    try:
        number = float(value)
        if integer:
            if not number.is_integer():
                raise ValueError
            return int(number)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        errors.append(f"{context}: '{value}' must be numeric")
        return None


def read_workbook(path: Path, base_settings_path: Path, output_dir: Path):
    workbook = load_workbook(path, data_only=False)
    missing = REQUIRED_SHEETS - set(workbook.sheetnames)
    if missing:
        raise ValueError(f"Workbook is missing sheets: {', '.join(sorted(missing))}")

    errors = []
    settings_values = {row[0].value: clean(row[1].value) for row in workbook["Settings"].iter_rows(min_row=7, max_col=2) if clean(row[0].value)}
    with base_settings_path.open(encoding="utf-8") as stream:
        base_settings = json.load(stream)

    project_root = base_settings_path.parent.parent
    schema_dir = project_root / "schemas"
    config_schema_prefix = Path(os.path.relpath(schema_dir, output_dir)).as_posix()
    lane_schema_prefix = Path(os.path.relpath(schema_dir, output_dir / "lanes")).as_posix()
    settings = {
        "$schema": f"{config_schema_prefix}/settings.schema.json",
        "title": str(settings_values.get("title") or "Software Portfolio Roadmap"),
        "subtitle": str(settings_values.get("subtitle") or ""),
        "start_year": numeric(settings_values.get("start_year"), "Settings start_year", errors, integer=True),
        "end_year": numeric(settings_values.get("end_year"), "Settings end_year", errors, integer=True),
        "rows_per_swim_lane": numeric(settings_values.get("rows_per_swim_lane"), "Settings rows_per_swim_lane", errors, integer=True),
        "lanes_directory": str(settings_values.get("lanes_directory") or "lanes"),
        "color_scheme": str(settings_values.get("color_scheme") or base_settings.get("color_scheme", "executive")),
        "color_schemes": base_settings["color_schemes"],
    }

    categories = []
    category_ids = set()
    category_rows = sorted(rows_by_header(workbook["Categories"]), key=lambda row: numeric(row.get("sort_order"), "Categories sort_order", errors) or 9999)
    for index, row in enumerate(category_rows, 1):
        if not row.get("category_id"):
            continue
        category_id = require_id(row["category_id"], f"Categories row {index}", errors)
        if category_id in category_ids:
            errors.append(f"Categories: duplicate category_id '{category_id}'")
        category_ids.add(category_id)
        categories.append({"id": category_id, "label": str(row.get("category_label") or category_id)})

    filter_groups = defaultdict(list)
    filter_labels = {}
    filter_defaults = {}
    filter_values = defaultdict(set)
    for index, row in enumerate(rows_by_header(workbook["Filters"]), 1):
        if not row.get("filter_id"):
            continue
        filter_id = require_id(row["filter_id"], f"Filters row {index} filter_id", errors)
        option_value = require_id(row.get("option_value"), f"Filters row {index} option_value", errors)
        label = str(row.get("filter_label") or filter_id)
        if filter_id in filter_labels and filter_labels[filter_id] != label:
            errors.append(f"Filters: filter_id '{filter_id}' has inconsistent labels")
        filter_labels[filter_id] = label
        if option_value in filter_values[filter_id]:
            errors.append(f"Filters: duplicate option '{option_value}' for '{filter_id}'")
        filter_values[filter_id].add(option_value)
        option = {"value": option_value, "label": str(row.get("option_label") or option_value), "_sort": numeric(row.get("sort_order"), f"Filters row {index} sort_order", errors) or 9999}
        filter_groups[filter_id].append(option)
        if truthy(row.get("is_default")):
            if filter_id in filter_defaults:
                errors.append(f"Filters: '{filter_id}' has more than one default")
            filter_defaults[filter_id] = option_value

    filters = []
    for filter_id, options in filter_groups.items():
        options.sort(key=lambda item: item.pop("_sort"))
        if filter_id not in filter_defaults:
            errors.append(f"Filters: '{filter_id}' needs exactly one default option")
        filters.append({"id": filter_id, "label": filter_labels[filter_id], "default": filter_defaults.get(filter_id), "options": options})

    lanes = []
    lane_ids = set()
    lane_rows = sorted(rows_by_header(workbook["Lanes"]), key=lambda row: numeric(row.get("sort_order"), "Lanes sort_order", errors) or 9999)
    for index, row in enumerate(lane_rows, 1):
        if not row.get("lane_id"):
            continue
        lane_id = require_id(row["lane_id"], f"Lanes row {index}", errors)
        if lane_id in lane_ids:
            errors.append(f"Lanes: duplicate lane_id '{lane_id}'")
        lane_ids.add(lane_id)
        lanes.append({
            "id": lane_id,
            "label": str(row.get("lane_label") or lane_id),
            "rows": numeric(row.get("rows"), f"Lanes row {index} rows", errors, integer=True),
            "sub_lane": truthy(row.get("sub_lane")),
            "entries": [],
        })
    settings["lane_order"] = [lane["id"] for lane in lanes]
    lanes_by_id = {lane["id"]: lane for lane in lanes}

    entry_filters = defaultdict(dict)
    for index, row in enumerate(rows_by_header(workbook["Entry Filters"]), 1):
        if not row.get("entry_id"):
            continue
        entry_id = str(row["entry_id"])
        filter_id = str(row.get("filter_id") or "")
        option_value = str(row.get("option_value") or "")
        if filter_id not in filter_values:
            errors.append(f"Entry Filters row {index}: unknown filter_id '{filter_id}'")
        elif option_value not in filter_values[filter_id]:
            errors.append(f"Entry Filters row {index}: '{option_value}' is not an option for '{filter_id}'")
        if filter_id in entry_filters[entry_id]:
            errors.append(f"Entry Filters: entry '{entry_id}' maps filter '{filter_id}' more than once")
        entry_filters[entry_id][filter_id] = option_value

    entry_ids = set()
    for index, row in enumerate(rows_by_header(workbook["Work Items"]), 1):
        if not row.get("entry_id"):
            continue
        entry_id = require_id(row["entry_id"], f"Work Items row {index}", errors)
        if entry_id in entry_ids:
            errors.append(f"Work Items: duplicate entry_id '{entry_id}'")
        entry_ids.add(entry_id)
        lane_id = str(row.get("lane_id") or "")
        if lane_id not in lanes_by_id:
            errors.append(f"Work Items row {index}: unknown lane_id '{lane_id}'")
            continue
        category_id = str(row.get("category_id") or "")
        if category_id not in category_ids:
            errors.append(f"Work Items row {index}: unknown category_id '{category_id}'")
        lane_row = numeric(row.get("row"), f"Work Items row {index} row", errors, integer=True)
        if lane_row and lanes_by_id[lane_id]["rows"] and lane_row > lanes_by_id[lane_id]["rows"]:
            errors.append(f"Work Items row {index}: row {lane_row} exceeds lane '{lane_id}' limit {lanes_by_id[lane_id]['rows']}")
        start = numeric(row.get("start"), f"Work Items row {index} start", errors)
        end = numeric(row.get("end"), f"Work Items row {index} end", errors)
        point = numeric(row.get("point"), f"Work Items row {index} point", errors)
        if point is None and (start is None or end is None):
            errors.append(f"Work Items row {index}: provide Start and End, or provide Point")
        if point is not None and (start is not None or end is not None):
            errors.append(f"Work Items row {index}: do not combine Point with Start or End")
        progress = numeric(row.get("progress_percent"), f"Work Items row {index} progress_percent", errors)
        label = str(row.get("label") or entry_id)
        if progress is not None:
            if not 0 <= progress <= 100:
                errors.append(f"Work Items row {index}: progress_percent must be from 0 to 100")
            elif "%" not in label:
                label = f"{label} - {progress:g}%"
        entry = {"id": entry_id, "label": label, "category": category_id, "row": lane_row, "detail": str(row.get("detail") or "")}
        predecessor_text = str(row.get("predecessor_ids") or "")
        predecessors = [value.strip() for value in re.split(r"[,;]", predecessor_text) if value.strip()]
        if predecessors:
            entry["predecessors"] = predecessors
        if point is not None:
            entry["point"] = point
        else:
            entry["start"], entry["end"] = start, end
        if entry_filters.get(entry_id):
            entry["when"] = entry_filters[entry_id]
        lanes_by_id[lane_id]["entries"].append(entry)

    unknown_mapping_entries = set(entry_filters) - entry_ids
    for entry_id in sorted(unknown_mapping_entries):
        errors.append(f"Entry Filters: unknown entry_id '{entry_id}'")
    all_entries = {entry["id"]: entry for lane in lanes for entry in lane["entries"]}
    for entry_id, entry in all_entries.items():
        predecessors = entry.get("predecessors", [])
        if len(predecessors) != len(set(predecessors)):
            errors.append(f"Work Items: entry '{entry_id}' repeats a predecessor")
        for predecessor_id in predecessors:
            if predecessor_id == entry_id:
                errors.append(f"Work Items: entry '{entry_id}' cannot depend on itself")
            elif predecessor_id not in all_entries:
                errors.append(f"Work Items: entry '{entry_id}' has unknown predecessor '{predecessor_id}'")
    visiting = set()
    visited = set()

    def visit(entry_id, trail):
        if entry_id in visiting:
            errors.append("Work Items dependency cycle: " + " -> ".join(trail))
            return
        if entry_id in visited:
            return
        visiting.add(entry_id)
        for predecessor_id in all_entries[entry_id].get("predecessors", []):
            if predecessor_id in all_entries:
                visit(predecessor_id, trail + [predecessor_id])
        visiting.remove(entry_id)
        visited.add(entry_id)

    for entry_id in all_entries:
        visit(entry_id, [entry_id])
    if not categories:
        errors.append("Categories: at least one category is required")
    if not lanes:
        errors.append("Lanes: at least one lane is required")
    if errors:
        raise ValueError("Workbook validation failed:\n- " + "\n- ".join(errors))
    return settings, categories, filters, lanes, config_schema_prefix, lane_schema_prefix


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def convert(workbook_path: Path, output_dir: Path, base_settings_path: Path):
    settings, categories, filters, lanes, config_schema_prefix, lane_schema_prefix = read_workbook(workbook_path, base_settings_path, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "lanes").mkdir(parents=True)
    write_json(output_dir / "settings.json", settings)
    write_json(output_dir / "categories.json", {"$schema": f"{config_schema_prefix}/categories.schema.json", "categories": categories})
    write_json(output_dir / "filters.json", {"$schema": f"{config_schema_prefix}/filters.schema.json", "filters": filters})
    for lane in lanes:
        lane_payload = {"$schema": f"{lane_schema_prefix}/lane.schema.json", **lane}
        write_json(output_dir / "lanes" / f"{lane['id']}.json", lane_payload)
    return len(lanes), sum(len(lane["entries"]) for lane in lanes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Completed Excel intake workbook")
    parser.add_argument("--output", "-o", type=Path, default=Path("config/from-excel"), help="Destination configuration folder")
    parser.add_argument("--base-settings", type=Path, default=Path("config/settings.json"), help="Existing settings.json used for color schemes")
    args = parser.parse_args()
    try:
        lane_count, entry_count = convert(args.workbook.resolve(), args.output.resolve(), args.base_settings.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Created roadmap JSON in: {args.output.resolve()}")
    print(f"Lanes: {lane_count} | Work items: {entry_count}")
    print(f"Next: python roadmap_generator.py \"{args.output}\" --output roadmap-from-excel.html")


if __name__ == "__main__":
    main()
