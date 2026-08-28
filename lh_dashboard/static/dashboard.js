async function refresh() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    const summary = document.getElementById("summary");
    if (summary) summary.textContent = data.tally.summary;

    const main = document.getElementById("projects");
    if (main) main.innerHTML = data.projects.map(renderProject).join("");
  } catch (err) {
    console.error("status refresh failed", err);
  }
}

function renderProject(project) {
  const note = project.note
    ? `<div class="project-note">${escapeHtml(project.note)}</div>`
    : "";
  return (
    `<section class="project"><h2>${escapeHtml(project.name)}</h2>${note}` +
    project.units.map(renderUnit).join("") +
    "</section>"
  );
}

function renderUnit(unit) {
  let html =
    `<article class="unit unit-${escapeHtml(unit.color)}">` +
    `<div class="unit-label">${escapeHtml(unit.label)}</div>` +
    `<div class="unit-state">${escapeHtml(unit.state_display)}</div>`;

  if (unit.note) {
    html += `<div class="unit-note">${escapeHtml(unit.note)}</div>`;
  }

  if (unit.oneshot) {
    if (unit.oneshot.in_progress) {
      html += `<div class="unit-detail">Last run: in progress — result pending</div>`;
    } else {
      if (unit.oneshot.finished_at) {
        html += `<div class="unit-detail">Finished: ${escapeHtml(unit.oneshot.finished_at)}</div>`;
      }
      if (unit.oneshot.exit_code !== null && unit.oneshot.exit_code !== undefined) {
        const ok = unit.oneshot.exit_ok;
        html +=
          `<div class="unit-detail ${ok ? "ok" : "fail"}">` +
          `Last exit: ${unit.oneshot.exit_code} (${ok ? "success" : "failed"})</div>`;
      }
    }
  } else if (unit.active_since) {
    html += `<div class="unit-detail">Active since: ${escapeHtml(unit.active_since)}</div>`;
  }

  if (unit.next_run) {
    html += `<div class="unit-detail">Next run: ${escapeHtml(unit.next_run)}</div>`;
  }
  if (unit.query_error) {
    html += `<div class="unit-detail fail">Query error: ${escapeHtml(unit.query_error)}</div>`;
  }
  for (const err of unit.recent_errors || []) {
    html += `<div class="unit-error">${escapeHtml(err)}</div>`;
  }

  html += "</article>";
  return html;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

refresh();
setInterval(refresh, 15000);
