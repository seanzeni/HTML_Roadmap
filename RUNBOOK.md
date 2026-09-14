# Swimlane Roadmap Runbook

This project turns simple JSON configuration files into one interactive HTML roadmap. Most users only need to edit files under `config/` and run the generator.

## Quick start

From PowerShell, run:

```powershell
python roadmap_generator.py
```

If the configuration is valid, the command creates `roadmap.html` and `roadmap.pdf` in the directory where the command was run. Both files are self-contained.

If Python is not available as `python`, run the script with the full path to your Python executable.

## Folder layout

```text
config/
├── settings.json          Overall dates, lane order, row limits, and color schemes
├── categories.json        Allowed work categories and legend labels
├── filters.json           Scenario selectors and their allowed values
└── lanes/
    ├── contracts.json     One file per swim lane
    ├── itso.json
    └── ...
static/
├── roadmap.css            Page appearance
└── roadmap.js             Drawing and interaction behavior
templates/
└── roadmap_template.html  HTML page structure
roadmap_generator.py       Validation and generation
roadmap.html               Generated output
roadmap.pdf                Printable decision-path output
```

## Normal update process

1. Edit one or more JSON files under `config/`.
2. Save the files.
3. Run `python roadmap_generator.py`.
4. Fix any validation errors shown in the terminal.
5. Refresh or reopen `roadmap.html`.

## Validate without creating files

Use this before sharing or committing configuration changes:

```powershell
python roadmap_generator.py --validate-only
```

The command checks every configuration file and reports errors without replacing the HTML or PDF. It also reports non-blocking overlap warnings.

## Generated date and user

The upper-right corner of the HTML and every PDF page shows the generation date, local time zone, and operating-system user. Override the displayed user when preparing a shared copy:

```powershell
python roadmap_generator.py --generated-by "Mainframe Engineering"
```

## Overlap warnings

The generator warns when two entries:

- Use the same swim lane and row.
- Overlap in time.
- Can be active under the same filter choices.

Mutually exclusive entries, such as IBM and Rocket alternatives or early and standard contract paths, are not treated as overlaps. Warnings do not stop output generation, but they should be reviewed because one bar may cover another.

## Start from the sample lane

Copy `examples/sample-lane.json` into `config/lanes/`, rename it, and update its lane ID, label, and entries. Then add the new lane ID to `lane_order` in `settings.json`.

The sample includes both a work bar and a decision point.

## Editor assistance with JSON Schema

Schema files are stored under `schemas/`. The configuration and sample files contain `$schema` references. Editors that support JSON Schema, including Visual Studio Code, can use these references for autocomplete and immediate warnings.

The schemas check each file's basic structure. The Python generator performs the cross-file checks, such as confirming that entry categories and filter criteria actually exist.

Do not edit `roadmap.html` directly. It is replaced each time the generator runs.

## Settings

Edit `config/settings.json` to control the whole roadmap.

- `title`: Main heading.
- `subtitle`: Short description below the heading.
- `start_year` and `end_year`: Visible timeline.
- `rows_per_swim_lane`: Default number of rows available in every lane.
- `lanes_directory`: Folder containing the lane files. Usually `lanes`.
- `lane_order`: Lane IDs in their display order. Every lane must appear exactly once.
- `color_scheme`: Name of the active scheme.
- `color_schemes`: Available named themes. Each theme contains UI colors and a category palette.

A lane may override the default row count with its own `rows` value. Rows are numbered starting at `1`. If a lane allows two rows, entries may use only row `1` or row `2`.

To change themes, set:

```json
"color_scheme": "ocean"
```

The included choices are `executive`, `ocean`, and `high-contrast`.

Each color scheme has a `category_palette` containing up to 10 colors. Colors should use standard CSS values such as `#2563eb`.

## Categories and the legend

Edit `config/categories.json` to define the allowed entry types. Each category automatically appears in the roadmap legend.

```json
{"id": "recovery", "label": "Recovery"}
```

- `id` is used by lane entries and must remain short and stable.
- `label` is shown to readers.

The order in this file selects the colors. The first category receives the first palette color, the second category receives the second color, and so on. You can define up to 10 categories.

Adding or renaming a category requires editing only `categories.json`. You do not need to add the category ID to each color scheme. Every scheme must contain at least as many palette colors as there are categories.

For example:

```json
"category_palette": ["#2563eb", "#7c3aed", "#0f766e"]
```

If the category order is Program, Contract, Recovery, those categories receive blue, purple, and green respectively. Reordering categories also changes their legend order and assigned colors.

## Filters and criteria

Edit `config/filters.json` to create scenario selectors.

```json
{
  "id": "solution",
  "label": "Selected SDLC Solution",
  "default": "ibm",
  "options": [
    {"value": "ibm", "label": "IBM suite viable"},
    {"value": "rocket", "label": "Rocket ChangeMan selected"}
  ]
}
```

An entry uses `when` to identify the scenario in which it is active:

```json
"when": {"solution": "ibm", "contract": "early"}
```

Every key in `when` must match a filter ID. Every value must match one of that filter's option values. An entry without `when` is active in every scenario.

## Swim-lane files

Create one JSON file for each swim lane under `config/lanes/`. The filename is for organization; the `id` inside the file is what links the configuration.

```json
{
  "id": "example-team",
  "label": "Example Team",
  "rows": 2,
  "entries": []
}
```

- `id`: Unique technical name. Use lowercase letters, numbers, hyphens, or underscores.
- `label`: Display name.
- `rows`: Optional lane-specific row limit. If omitted, the setting in `rows_per_swim_lane` is used.
- `sub_lane`: Optional `true` or `false`. A sub-lane receives a shaded background.
- `entries`: Work bars and decision points in this lane.

After creating a lane file, add its ID to `lane_order` in `settings.json`.

## Adding a work bar

```json
{
  "id": "dr-planning",
  "start": 2027,
  "end": 2028,
  "label": "DR Planning",
  "category": "recovery",
  "row": 2,
  "when": {"solution": "ibm"},
  "detail": "Design disaster recovery for GitHub, Artifactory, and DevOps Deploy."
}
```

- `id`: Unique across the entire roadmap.
- `start`: Beginning of the bar. Decimal years are allowed, such as `2029.5`.
- `end`: End of the bar. The end is treated as the boundary after the final covered period.
- `label`: Short text shown inside the bar. Long labels wrap to two lines and are clipped to the bar.
- `category`: Must exist in `categories.json`.
- `row`: Must be between `1` and the lane's row limit.
- `when`: Optional filter criteria.
- `detail`: Longer explanation shown when the active bar is selected.

## Adding a decision point

Use `point` instead of `start` and `end`:

```json
{
  "id": "solution-decision",
  "point": 2026.92,
  "label": "Solution Decision",
  "category": "decision",
  "row": 2,
  "detail": "Determine whether the IBM suite is viable."
}
```

Do not put `point` and `start`/`end` on the same entry.

## Validation rules

The generator checks that:

- All JSON files are valid JSON.
- Required settings are present.
- IDs use the correct format and are unique.
- Each lane appears exactly once in `lane_order`.
- Each entry uses a known category.
- No more than 10 categories are defined.
- Every color scheme provides enough ordered palette colors for the categories.
- Filter defaults and entry criteria use allowed values.
- Each entry uses a row within its lane's limit.
- Each entry is either a work bar or a decision point.

Validation reports all detected configuration problems together. The HTML file is not replaced when validation fails.

## Common errors

`unknown category`: Add the category to `categories.json`, or correct the entry spelling.

`needs at least ... palette colors`: Add more colors to that scheme's `category_palette`, or reduce the number of categories.

`unknown filter criterion`: Correct the key inside `when`, or define the filter in `filters.json`.

`invalid value for filter`: Use one of the filter's exact option values.

`row is outside the allowed range`: Increase the lane's `rows` value or move the entry to a valid row.

`lane_order is missing lanes`: Add the lane ID to `settings.json`.

## Choosing the output name and location

Use `--output` or its shorter form, `-o`:

```powershell
python roadmap_generator.py --output leadership-roadmap.html
python roadmap_generator.py -o reports\modernization-roadmap.html
```

If the filename has no extension, the generator adds `.html`:

```powershell
python roadmap_generator.py -o reports\modernization-roadmap
```

If the output folder does not exist, the generator creates it. When `--output` is omitted, the default is `roadmap.html` in the current working directory. The PDF normally uses the same folder and base name:

```powershell
python roadmap_generator.py -o reports\leadership-roadmap.html
# Creates reports\leadership-roadmap.html and reports\leadership-roadmap.pdf
```

Choose a different PDF location with:

```powershell
python roadmap_generator.py --pdf-output printable\roadmap-for-review.pdf
```

## Understanding the printable PDF

The PDF contains one page for every possible combination of filter choices. Each page begins with a **Decision Path** line, such as:

```text
Contract Path: Early renewal | Selected SDLC Solution: IBM suite viable
```

Each decision path begins with a visual timeline followed by one or more **Path Details** pages. The written pages list active entries in chronological order and include the full `detail` text from the lane files.

Only entries active for that exact decision path appear in its timeline and write-up. Unconditional entries appear in every applicable path. This avoids relying on faded colors in printed copies and makes each flow understandable when pages are separated.

## Exporting one selected path from the HTML

Open `roadmap.html`, choose the contract and solution filters, and select **Export selected path**. The browser downloads a PDF containing:

1. The timeline for the currently selected decision path.
2. Written detail pages for only the entries active in that path.

The filename includes the selected filter values, such as `roadmap-early-ibm.pdf`. This is a file download; it does not send anything to a physical printer or open the print dialog.

The PDF export library is bundled inside `roadmap.html`, so this feature works when the HTML is opened locally or shared without the source folders.

## Custom configuration location

Pass a configuration folder as the optional positional argument. Combine it with `--output` when needed:

```powershell
python roadmap_generator.py C:\Roadmaps\MyConfig --output C:\Roadmaps\MyRoadmap.html
```

The HTML template, CSS, and JavaScript remain next to the generator. The selected configuration folder must contain `settings.json`, `categories.json`, `filters.json`, and its lane directory.
