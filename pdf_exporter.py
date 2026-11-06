"""Create a printable, scenario-separated PDF from validated roadmap data."""

from __future__ import annotations

from itertools import product
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


def _ascii_text(value: object) -> str:
    return (str(value).replace("–", "-").replace("—", "-").replace("‑", "-")
            .replace("“", '"').replace("”", '"').replace("’", "'"))


def _scenario_combinations(data: dict):
    groups = data["scenario_groups"]
    if not groups:
        yield {}, "All entries"
        return
    # Portfolio filters use an explicit "all" wildcard. Printing every possible
    # facet combination creates hundreds of repetitive pages, so emit one useful
    # all-work overview. Scenario roadmaps without wildcard options retain the
    # original one-page-set-per-decision-path behavior.
    if all(any(option["value"] == "all" for option in group["options"]) for group in groups):
        yield {group["id"]: "all" for group in groups}, "All workstreams and owners"
        return
    for options in product(*(group["options"] for group in groups)):
        state = {group["id"]: option["value"] for group, option in zip(groups, options)}
        label = " | ".join(f"{_ascii_text(group['label'])}: {_ascii_text(option['label'])}" for group, option in zip(groups, options))
        yield state, label


def _active(entry: dict, state: dict) -> bool:
    return all(state.get(key) == "all" or state.get(key) == value for key, value in entry.get("when", {}).items())


def _shorten(text: str, max_width: float, font: str, size: float) -> str:
    if stringWidth(text, font, size) <= max_width:
        return text
    shortened = text
    while shortened and stringWidth(shortened + "...", font, size) > max_width:
        shortened = shortened[:-1]
    return shortened.rstrip() + "..."


def _entry_time(entry: dict) -> str:
    if "point" in entry:
        return f"Decision at {entry['point']:g}"
    return f"{entry['start']:g}-{entry['end']:g}"


def _draw_detail_pages(canvas: Canvas, data: dict, state: dict, path_label: str,
                       page_width: float, page_height: float, ui: dict,
                       category_colors: dict, category_labels: dict) -> None:
    lane_labels = {lane["id"]: lane["label"] for lane in data["lanes"]}
    lane_order = {lane["id"]: index for index, lane in enumerate(data["lanes"])}
    entries = sorted(
        (entry for entry in data["entries"] if _active(entry, state)),
        key=lambda entry: (entry.get("point", entry.get("start", 0)), lane_order[entry["lane"]], entry["row"]),
    )
    page_index = 0
    y = 0.0

    def start_page() -> float:
        nonlocal page_index
        page_index += 1
        canvas.setFillColor(ui["background"])
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setFillColor(ui["foreground"])
        canvas.setFont("Helvetica-Bold", 18)
        heading = "Path Details" if page_index == 1 else "Path Details (continued)"
        canvas.drawString(28, page_height - 32, heading)
        canvas.setFillColor(ui["muted"])
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(page_width - 28, page_height - 24, f"Generated: {_ascii_text(data['generated_at'])}")
        canvas.drawRightString(page_width - 28, page_height - 34, f"By: {_ascii_text(data['generated_by'])}")
        canvas.setFillColor(ui["foreground"])
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(28, page_height - 50, "DECISION PATH")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(105, page_height - 50, _shorten(path_label, page_width - 140, "Helvetica", 9))
        canvas.setStrokeColor(ui["line"])
        canvas.line(28, page_height - 62, page_width - 28, page_height - 62)
        return page_height - 79

    y = start_page()
    for entry in entries:
        detail_lines = simpleSplit(_ascii_text(entry.get("detail", "")), "Helvetica", 8, page_width - 92)
        item_height = 25 + max(1, len(detail_lines)) * 10
        if y - item_height < 34:
            canvas.showPage()
            y = start_page()
        canvas.setFillColor(category_colors[entry["category"]])
        canvas.rect(30, y - 9, 7, 7, fill=1, stroke=0)
        canvas.setFillColor(ui["foreground"])
        canvas.setFont("Helvetica-Bold", 9)
        summary = f"{_entry_time(entry)} | {lane_labels[entry['lane']]} | {category_labels[entry['category']]} | {_ascii_text(entry['label'])}"
        canvas.drawString(44, y - 9, _shorten(summary, page_width - 76, "Helvetica-Bold", 9))
        canvas.setFont("Helvetica", 8)
        line_y = y - 22
        for line in detail_lines or [""]:
            canvas.drawString(44, line_y, line)
            line_y -= 10
        canvas.setStrokeColor(ui["line"])
        canvas.line(44, line_y + 3, page_width - 28, line_y + 3)
        y -= item_height
    canvas.setFillColor(ui["muted"])
    canvas.setFont("Helvetica", 7)
    canvas.drawString(28, 20, "Written flow for the decision path shown above.")
    canvas.showPage()


def export_pdf(data: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(letter)
    canvas = Canvas(str(destination), pagesize=(page_width, page_height))
    canvas.setTitle(_ascii_text(data["title"]))
    canvas.setSubject("Printable swimlane roadmap with one page per decision path")
    canvas.setAuthor("Roadmap Generator")
    ui = {key: HexColor(value) for key, value in data["theme"]["ui"].items()}
    category_colors = {key: HexColor(value) for key, value in data["theme"]["categories"].items()}
    category_labels = {item["id"]: item["label"] for item in data["categories"]}

    for page_number, (state, path_label) in enumerate(_scenario_combinations(data), start=1):
        canvas.setFillColor(ui["background"])
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setFillColor(ui["foreground"])
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(28, page_height - 32, _ascii_text(data["title"]))
        canvas.setFillColor(ui["muted"])
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(page_width - 28, page_height - 24, f"Generated: {_ascii_text(data['generated_at'])}")
        canvas.drawRightString(page_width - 28, page_height - 34, f"By: {_ascii_text(data['generated_by'])}")
        canvas.setFillColor(ui["foreground"])
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(28, page_height - 50, "DECISION PATH")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(105, page_height - 50, _shorten(path_label, page_width - 140, "Helvetica", 9))

        legend_x = 28
        legend_y = page_height - 68
        for category in data["categories"]:
            canvas.setFillColor(category_colors[category["id"]])
            canvas.rect(legend_x, legend_y - 4, 12, 7, fill=1, stroke=0)
            canvas.setFillColor(ui["foreground"])
            canvas.setFont("Helvetica", 7)
            category_label = _ascii_text(category["label"])
            canvas.drawString(legend_x + 16, legend_y - 3, category_label)
            legend_x += 20 + stringWidth(category_label, "Helvetica", 7)

        left, right, chart_top, chart_bottom = 118, 24, page_height - 88, 42
        chart_width = page_width - left - right
        span = data["end_year"] - data["start_year"] + 1
        x = lambda year: left + (year - data["start_year"]) / span * chart_width
        total_rows = sum(lane["rows"] for lane in data["lanes"])
        header_space = 16 * len(data["lanes"])
        row_height = min(20, (chart_top - chart_bottom - header_space) / total_rows)
        lane_y = chart_top

        canvas.setStrokeColor(ui["line"])
        for year in range(data["start_year"], data["end_year"] + 1):
            px = x(year)
            canvas.line(px, chart_bottom, px, chart_top)
            canvas.setFillColor(ui["muted"])
            canvas.setFont("Helvetica", 8)
            canvas.drawString(px + 3, chart_top + 3, str(year))
        canvas.line(x(data["end_year"] + 1), chart_bottom, x(data["end_year"] + 1), chart_top)

        for lane in data["lanes"]:
            lane_height = 16 + lane["rows"] * row_height
            lane_bottom = lane_y - lane_height
            if lane.get("sub_lane"):
                canvas.setFillColor(ui["sub_lane"])
                canvas.rect(24, lane_bottom, page_width - 48, lane_height, fill=1, stroke=0)
            canvas.setFillColor(ui["foreground"])
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(28 if not lane.get("sub_lane") else 38, lane_y - 11, _ascii_text(lane["label"]))
            canvas.setStrokeColor(ui["line"])
            canvas.line(24, lane_bottom, page_width - 24, lane_bottom)
            for entry in (item for item in data["entries"] if item["lane"] == lane["id"] and _active(item, state)):
                y = lane_y - 16 - (entry["row"] + 1) * row_height + 3
                color = category_colors[entry["category"]]
                canvas.setFillColor(color)
                if "point" in entry:
                    px = x(entry["point"])
                    canvas.saveState()
                    canvas.translate(px, y + row_height / 2)
                    canvas.rotate(45)
                    canvas.rect(-4, -4, 8, 8, fill=1, stroke=0)
                    canvas.restoreState()
                    canvas.setFillColor(ui["foreground"])
                    canvas.setFont("Helvetica-Bold", 6.5)
                    canvas.drawString(px + 8, y + row_height / 2 - 2, _ascii_text(entry["label"]))
                else:
                    start = x(entry["start"])
                    end = x(min(entry["end"], data["end_year"] + 1))
                    bar_width = max(5, end - start - 2)
                    canvas.roundRect(start, y, bar_width, row_height - 6, 2, fill=1, stroke=0)
                    canvas.setFillColor(ui["bar_text"])
                    canvas.setFont("Helvetica-Bold", 6.5)
                    canvas.drawString(start + 3, y + (row_height - 8) / 2, _shorten(_ascii_text(entry["label"]), bar_width - 6, "Helvetica-Bold", 6.5))
            lane_y = lane_bottom

        canvas.setFillColor(ui["muted"])
        canvas.setFont("Helvetica", 7)
        canvas.drawString(28, 22, f"Decision-path view {page_number} - Only entries active for this path are shown.")
        canvas.drawRightString(page_width - 28, 22, f"Theme: {data['theme_name']}")
        canvas.showPage()
        _draw_detail_pages(canvas, data, state, path_label, page_width, page_height, ui, category_colors, category_labels)

    canvas.save()
