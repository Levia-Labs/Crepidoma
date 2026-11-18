"use strict";
/* Rows place a bar over unit columns: start is the 0-based first unit, span the number of units. */
R.types.timeline = function (sec, host) {
  var units = sec.units || [];
  var grid = R.el("div", { class: "tl" });
  grid.style.gridTemplateColumns =
    "minmax(140px,220px) repeat(" + units.length + ",minmax(40px,1fr))";
  grid.appendChild(R.el("div"));
  units.forEach(function (u) {
    grid.appendChild(R.el("div", { class: "unit", text: u }));
  });
  (sec.rows || []).forEach(function (row, i) {
    var label = R.text("div", { class: "label" }, row.label);
    R.tip(label, row.note);
    label.style.gridArea = i + 2 + " / 1";
    grid.appendChild(label);
    var attrs = { class: "bar t-" + row.tone, "aria-label": row.label };
    var bar = R.el(row.target ? "button" : "div", attrs);
    if (row.target) {
      bar.setAttribute("type", "button");
      bar.addEventListener("click", function () {
        var target = document.getElementById(row.target);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    bar.style.gridColumn = (Number(row.start) || 0) + 2 + " / span " + (Number(row.span) || 1);
    bar.style.gridRow = String(i + 2);
    grid.appendChild(bar);
  });
  host.appendChild(R.el("div", { class: "tl-box" }, [grid]));
};
