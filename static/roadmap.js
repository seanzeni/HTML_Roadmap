(() => {
  const data = JSON.parse(document.getElementById("roadmap-data").textContent);
  const svg = document.querySelector("svg");
  const controls = document.getElementById("controls");
  const detail = document.querySelector(".detail");
  const mobile = document.querySelector(".mobile");
  const legend = document.getElementById("legend");
  const ns = "http://www.w3.org/2000/svg";
  const state = {};

  const uiVariableNames = {
    background: "--bg", foreground: "--fg", muted: "--muted", line: "--line",
    panel: "--panel", sub_lane: "--sub", bar_text: "--bar-text",
  };
  Object.entries(data.theme.ui).forEach(([name, color]) => {
    document.documentElement.style.setProperty(uiVariableNames[name], color);
  });
  data.categories.forEach((category) => {
    document.documentElement.style.setProperty(`--${category.id}`, data.theme.categories[category.id]);
    const item = document.createElement("span");
    item.innerHTML = `<i class="swatch" style="--category-color:${data.theme.categories[category.id]}"></i>${category.label}`;
    legend.append(item);
  });

  document.title = data.title;
  document.getElementById("heading").textContent = data.title;
  document.getElementById("subtitle").textContent = `${data.start_year}–${data.end_year} · ${data.subtitle}`;
  document.getElementById("generated-meta").textContent = `Generated ${data.generated_at} · ${data.generated_by}`;

  data.scenario_groups.forEach((group) => {
    state[group.id] = group.default;
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.htmlFor = `scenario-${group.id}`;
    label.textContent = group.label;
    const select = document.createElement("select");
    select.id = `scenario-${group.id}`;
    group.options.forEach((option) => {
      const item = document.createElement("option");
      item.value = option.value;
      item.textContent = option.label;
      item.selected = option.value === group.default;
      select.append(item);
    });
    select.addEventListener("change", () => { state[group.id] = select.value; draw(); });
    field.append(label, select);
    controls.append(field);
  });

  function node(name, attributes = {}, text = "") {
    const element = document.createElementNS(ns, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (text) element.textContent = text;
    return element;
  }

  function visible(entry) {
    return !entry.when || Object.entries(entry.when).every(([key, value]) => state[key] === value);
  }

  function wrappedLines(label, width) {
    const limit = Math.max(4, Math.floor((width - 12) / 6.2));
    const lines = [""];
    for (const word of label.split(/\s+/)) {
      const candidate = `${lines.at(-1)} ${word}`.trim();
      if (candidate.length <= limit) lines[lines.length - 1] = candidate;
      else if (lines.length < 2) lines.push(word);
      else {
        const current = lines[1];
        lines[1] = (current.length + word.length + 1 <= limit ? `${current} ${word}` : current)
          .slice(0, Math.max(1, limit - 1)) + "…";
        break;
      }
    }
    return lines;
  }

  function drawDecision(entry, y, active, x) {
    const px = x(entry.point);
    const size = 7;
    const path = `M ${px} ${y} l ${size} ${size} l ${-size} ${size} l ${-size} ${-size} Z`;
    const show = () => { detail.textContent = `${entry.label} — ${entry.detail || ""}`; };
    svg.append(node("path", { d: path, class: "decision", opacity: active ? 1 : 0.14, style: `--category-color:${data.theme.categories[entry.category]}` }));
    if (active) {
      const text = node("text", { x: px + 12, y: y + 11, class: "bar-text decision-text" }, entry.label);
      text.addEventListener("click", show);
      svg.append(text);
    }
    const hitAttributes = { x: px - 10, y: y - 8, width: Math.max(44, entry.label.length * 7 + 32), height: 36, class: `decision-hit${active ? "" : " is-inactive"}` };
    if (active) Object.assign(hitAttributes, { role: "button", tabindex: 0, "aria-label": `${entry.label}. ${entry.detail || ""}` });
    else hitAttributes["aria-hidden"] = "true";
    const hit = node("rect", hitAttributes);
    if (active) {
      hit.addEventListener("click", show);
      hit.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(); }
      });
    }
    svg.append(hit);
  }

  function drawBar(entry, index, y, active, x) {
    const start = x(entry.start);
    const end = x(Math.min(entry.end, data.end_year + 1));
    const width = Math.max(7, end - start - 3);
    const height = 23;
    const clipId = `bar-clip-${index}`;
    const defs = svg.querySelector("defs") || svg.insertBefore(node("defs"), svg.firstChild);
    const clip = node("clipPath", { id: clipId });
    clip.append(node("rect", { x: start + 3, y, width: Math.max(1, width - 6), height }));
    defs.append(clip);
    const barAttributes = { x: start, y, width, height, rx: 3, class: `bar ${entry.category || "program"}${active ? "" : " is-inactive"}`, opacity: active ? 1 : 0.13 };
    if (active) barAttributes["aria-label"] = `${entry.label}. ${entry.detail || ""}`;
    else barAttributes["aria-hidden"] = "true";
    barAttributes.fill = data.theme.categories[entry.category];
    const bar = node("rect", barAttributes);
    if (active) bar.addEventListener("click", () => { detail.textContent = `${entry.label} — ${entry.detail || ""}`; });
    svg.append(bar);
    if (active && width > 34) {
      const text = node("text", { x: start + 6, y: y + 9, class: "bar-text", "clip-path": `url(#${clipId})` });
      wrappedLines(entry.label, width).forEach((line, lineIndex) => text.append(node("tspan", { x: start + 6, dy: lineIndex ? 11 : 0 }, line)));
      svg.append(text);
    }
  }

  function draw() {
    svg.replaceChildren();
    const width = 1200, left = 180, right = 12, top = 38, bottom = 20;
    const laneHeights = data.lanes.map((lane) => 42 + lane.rows * 25);
    const laneTops = [];
    laneHeights.reduce((current, laneHeight) => { laneTops.push(current); return current + laneHeight; }, top);
    const height = top + laneHeights.reduce((total, laneHeight) => total + laneHeight, 0) + bottom;
    const span = data.end_year - data.start_year + 1;
    const plotWidth = width - left - right;
    const x = (year) => left + ((year - data.start_year) / span) * plotWidth;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.append(node("title", { id: "svg-title" }, data.title));
    svg.append(node("desc", { id: "svg-desc" }, "Interactive swimlane roadmap. Use the scenario selectors to compare paths."));

    for (let year = data.start_year; year <= data.end_year; year += 1) {
      const px = x(year);
      svg.append(node("line", { x1: px, y1: top - 5, x2: px, y2: height - bottom, class: "year-line" }));
      svg.append(node("text", { x: px + 4, y: 20, class: "axis-text", "font-size": 13 }, String(year)));
    }
    svg.append(node("line", { x1: x(data.end_year + 1), y1: top - 5, x2: x(data.end_year + 1), y2: height - bottom, class: "year-line" }));

    data.lanes.forEach((lane, index) => {
      const y = laneTops[index];
      if (lane.sub_lane) svg.append(node("rect", { x: 0, y, width, height: laneHeights[index], class: "sub-bg" }));
      svg.append(node("line", { x1: 0, y1: y + laneHeights[index], x2: width, y2: y + laneHeights[index], class: "lane-line" }));
      svg.append(node("text", { x: lane.sub_lane ? 20 : 5, y: y + 18, class: "lane-text", "font-size": 13, "font-weight": 600 }, lane.label));
    });

    data.entries.forEach((entry, index) => {
      const laneIndex = data.lanes.findIndex((lane) => lane.id === entry.lane);
      const y = laneTops[laneIndex] + 28 + (entry.row || 0) * 25;
      if (entry.point !== undefined) drawDecision(entry, y, visible(entry), x);
      else drawBar(entry, index, y, visible(entry), x);
    });

    mobile.innerHTML = data.entries.filter(visible).map((entry) => {
      const lane = data.lanes.find((item) => item.id === entry.lane);
      const timing = entry.point !== undefined ? `Decision: ${Math.floor(entry.point)}` : `${entry.start}–${Math.min(entry.end, data.end_year + 1)}`;
      return `<div><strong>${lane.label}: ${entry.label}</strong><span>${timing}</span></div>`;
    }).join("");
    detail.textContent = "Select a bar or decision point for its description. Faded items belong to another scenario.";
  }

  function ascii(text) {
    return String(text).replace(/[–—‑]/g, "-").replace(/[“”]/g, '"').replace(/’/g, "'");
  }

  function selectedPathLabel() {
    return data.scenario_groups.map((group) => {
      const option = group.options.find((item) => item.value === state[group.id]);
      return `${group.label}: ${option.label}`;
    }).join(" | ");
  }

  function pdfColor(hex) {
    const value = hex.replace("#", "");
    return PDFLib.rgb(parseInt(value.slice(0, 2), 16) / 255, parseInt(value.slice(2, 4), 16) / 255, parseInt(value.slice(4, 6), 16) / 255);
  }

  function fitPdfText(text, font, size, maxWidth) {
    const clean = ascii(text);
    if (font.widthOfTextAtSize(clean, size) <= maxWidth) return clean;
    let result = clean;
    while (result && font.widthOfTextAtSize(`${result}...`, size) > maxWidth) result = result.slice(0, -1);
    return `${result.trim()}...`;
  }

  function wrapPdfText(text, font, size, maxWidth) {
    const lines = [];
    let line = "";
    ascii(text).split(/\s+/).forEach((word) => {
      const candidate = `${line} ${word}`.trim();
      if (!line || font.widthOfTextAtSize(candidate, size) <= maxWidth) line = candidate;
      else { lines.push(line); line = word; }
    });
    if (line) lines.push(line);
    return lines.length ? lines : [""];
  }

  async function exportSelectedPath() {
    const button = document.getElementById("export-selected");
    button.disabled = true;
    button.textContent = "Creating PDF...";
    try {
      const { PDFDocument, StandardFonts } = PDFLib;
      const pdfDocument = await PDFDocument.create();
      pdfDocument.setTitle(`${ascii(data.title)} - Selected Decision Path`);
      pdfDocument.setSubject(ascii(selectedPathLabel()));
      const regular = await pdfDocument.embedFont(StandardFonts.Helvetica);
      const bold = await pdfDocument.embedFont(StandardFonts.HelveticaBold);
      const ui = Object.fromEntries(Object.entries(data.theme.ui).map(([key, value]) => [key, pdfColor(value)]));
      const colors = Object.fromEntries(Object.entries(data.theme.categories).map(([key, value]) => [key, pdfColor(value)]));
      const pathLabel = ascii(selectedPathLabel());
      const activeEntries = data.entries.filter(visible).sort((a, b) =>
        (a.point ?? a.start) - (b.point ?? b.start) || data.lanes.findIndex((lane) => lane.id === a.lane) - data.lanes.findIndex((lane) => lane.id === b.lane));
      const pageWidth = 792, pageHeight = 612;

      function addHeader(page, heading) {
        page.drawRectangle({ x: 0, y: 0, width: pageWidth, height: pageHeight, color: ui.background });
        page.drawText(heading, { x: 28, y: 576, size: 18, font: bold, color: ui.foreground });
        page.drawText(`Generated: ${ascii(data.generated_at)}`, { x: 590, y: 584, size: 6.5, font: regular, color: ui.muted });
        page.drawText(`By: ${ascii(data.generated_by)}`, { x: 590, y: 574, size: 6.5, font: regular, color: ui.muted });
        page.drawText("DECISION PATH", { x: 28, y: 557, size: 9, font: bold, color: ui.foreground });
        page.drawText(fitPdfText(pathLabel, regular, 9, 625), { x: 105, y: 557, size: 9, font: regular, color: ui.foreground });
      }

      const timeline = pdfDocument.addPage([pageWidth, pageHeight]);
      addHeader(timeline, ascii(data.title));
      let legendX = 28;
      data.categories.forEach((category) => {
        timeline.drawRectangle({ x: legendX, y: 535, width: 12, height: 7, color: colors[category.id] });
        timeline.drawText(ascii(category.label), { x: legendX + 16, y: 534, size: 7, font: regular, color: ui.foreground });
        legendX += 22 + regular.widthOfTextAtSize(ascii(category.label), 7);
      });

      const left = 118, right = 24, chartTop = 520, chartBottom = 38;
      const chartWidth = pageWidth - left - right;
      const yearSpan = data.end_year - data.start_year + 1;
      const x = (year) => left + ((year - data.start_year) / yearSpan) * chartWidth;
      const totalUnits = data.lanes.reduce((sum, lane) => sum + 0.65 + lane.rows, 0);
      const unit = (chartTop - chartBottom) / totalUnits;
      const lanePositions = [];
      let laneTop = chartTop;
      data.lanes.forEach((lane) => {
        const laneHeight = unit * (0.65 + lane.rows);
        lanePositions.push({ top: laneTop, bottom: laneTop - laneHeight, rowHeight: unit });
        laneTop -= laneHeight;
      });
      for (let year = data.start_year; year <= data.end_year + 1; year += 1) {
        const px = x(year);
        timeline.drawLine({ start: { x: px, y: chartBottom }, end: { x: px, y: chartTop }, thickness: 0.7, color: ui.line });
        if (year <= data.end_year) timeline.drawText(String(year), { x: px + 3, y: chartTop + 3, size: 8, font: regular, color: ui.muted });
      }
      data.lanes.forEach((lane, laneIndex) => {
        const position = lanePositions[laneIndex];
        if (lane.sub_lane) timeline.drawRectangle({ x: 24, y: position.bottom, width: pageWidth - 48, height: position.top - position.bottom, color: ui.sub_lane });
        timeline.drawText(ascii(lane.label), { x: lane.sub_lane ? 38 : 28, y: position.top - 12, size: 8, font: bold, color: ui.foreground });
        timeline.drawLine({ start: { x: 24, y: position.bottom }, end: { x: pageWidth - 24, y: position.bottom }, thickness: 0.7, color: ui.line });
      });
      activeEntries.forEach((entry) => {
        const laneIndex = data.lanes.findIndex((lane) => lane.id === entry.lane);
        const position = lanePositions[laneIndex];
        const y = position.top - unit * (entry.row + 1.15);
        if (entry.point !== undefined) {
          const px = x(entry.point);
          timeline.drawRectangle({ x: px - 4, y, width: 8, height: 8, rotate: PDFLib.degrees(45), color: colors[entry.category] });
          timeline.drawText(ascii(entry.label), { x: px + 9, y: y + 1, size: 6.5, font: bold, color: ui.foreground });
        } else {
          const start = x(entry.start), end = x(Math.min(entry.end, data.end_year + 1));
          const barWidth = Math.max(5, end - start - 2), barHeight = Math.max(9, unit - 5);
          timeline.drawRectangle({ x: start, y, width: barWidth, height: barHeight, color: colors[entry.category] });
          timeline.drawText(fitPdfText(entry.label, bold, 6.5, barWidth - 6), { x: start + 3, y: y + Math.max(2, (barHeight - 6.5) / 2), size: 6.5, font: bold, color: ui.bar_text });
        }
      });
      timeline.drawText("Selected decision path - only active entries are shown.", { x: 28, y: 20, size: 7, font: regular, color: ui.muted });

      let detailsPage, cursorY;
      function newDetailsPage(continued = false) {
        detailsPage = pdfDocument.addPage([pageWidth, pageHeight]);
        addHeader(detailsPage, continued ? "Path Details (continued)" : "Path Details");
        detailsPage.drawLine({ start: { x: 28, y: 545 }, end: { x: pageWidth - 28, y: 545 }, thickness: 0.7, color: ui.line });
        cursorY = 526;
      }
      newDetailsPage();
      const laneLabels = Object.fromEntries(data.lanes.map((lane) => [lane.id, lane.label]));
      const categoryLabels = Object.fromEntries(data.categories.map((category) => [category.id, category.label]));
      activeEntries.forEach((entry) => {
        const timing = entry.point !== undefined ? `Decision at ${entry.point}` : `${entry.start}-${entry.end}`;
        const summary = `${timing} | ${laneLabels[entry.lane]} | ${categoryLabels[entry.category]} | ${entry.label}`;
        const lines = wrapPdfText(entry.detail || "", regular, 8, pageWidth - 92);
        const requiredHeight = 25 + lines.length * 10;
        if (cursorY - requiredHeight < 34) newDetailsPage(true);
        detailsPage.drawRectangle({ x: 30, y: cursorY - 8, width: 7, height: 7, color: colors[entry.category] });
        detailsPage.drawText(fitPdfText(summary, bold, 9, pageWidth - 76), { x: 44, y: cursorY - 8, size: 9, font: bold, color: ui.foreground });
        let lineY = cursorY - 21;
        lines.forEach((line) => { detailsPage.drawText(line, { x: 44, y: lineY, size: 8, font: regular, color: ui.foreground }); lineY -= 10; });
        detailsPage.drawLine({ start: { x: 44, y: lineY + 3 }, end: { x: pageWidth - 28, y: lineY + 3 }, thickness: 0.5, color: ui.line });
        cursorY -= requiredHeight;
      });

      const bytes = await pdfDocument.save();
      const blob = new Blob([bytes], { type: "application/pdf" });
      const link = document.createElement("a");
      const values = data.scenario_groups.map((group) => state[group.id]).join("-");
      link.href = URL.createObjectURL(blob);
      link.download = `roadmap-${values || "selected"}.pdf`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      detail.textContent = `Exported ${link.download}`;
    } catch (error) {
      detail.textContent = `Export failed: ${error.message}`;
    } finally {
      button.disabled = false;
      button.textContent = "Export selected path";
    }
  }

  document.getElementById("export-selected").addEventListener("click", exportSelectedPath);

  draw();
})();
