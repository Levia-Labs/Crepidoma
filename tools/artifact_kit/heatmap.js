"use strict";
/* Heatmap of rows x columns. A diverging scale is centred on 0 (e.g. correlations -1..1); hovering or focusing a
   cell highlights its row and column and reads the value in the strip. */
R.types.heatmap = function (sec, host) {
  var diverging = sec.scale === "diverging";
  var values = {},
    lo = Infinity,
    hi = -Infinity;
  sec.cells.forEach(function (c) {
    values[c[0] + "\u0000" + c[1]] = c[2];
    lo = Math.min(lo, c[2]);
    hi = Math.max(hi, c[2]);
  });
  var span = Math.max(Math.abs(lo), Math.abs(hi)) || 1;

  /* class suffix and ink flag of a value */
  function step(v) {
    if (diverging) {
      var n = Math.round((v / span) * 4);
      return { cls: n === 0 ? "0" : (n < 0 ? "n" : "p") + Math.abs(n), hi: Math.abs(n) >= 3 };
    }
    var l = hi === lo ? 3 : 1 + Math.round(((v - lo) / (hi - lo)) * 4);
    return { cls: "s" + l, hi: l >= 4 };
  }

  var strip = R.strip();
  var rowHeads = {},
    colHeads = {},
    cellEls = [];
  var head = R.el("tr", {}, [R.el("td")]);
  sec.cols.forEach(function (c) {
    var th = R.el("th", { text: c });
    colHeads[c] = th;
    head.appendChild(th);
  });
  var body = R.el("tbody");
  var best = null;
  sec.rows.forEach(function (r) {
    var th = R.el("th", { text: r });
    rowHeads[r] = th;
    var tr = R.el("tr", {}, [th]);
    sec.cols.forEach(function (c) {
      var v = values[r + "\u0000" + c],
        td = R.el("td");
      if (v !== undefined) {
        var st = step(v);
        var b = R.el("button", {
          type: "button",
          class: "cell h-" + st.cls + (st.hi ? " hi" : ""),
          text: R.fmt(v),
        });
        b.setAttribute("aria-label", r + ", " + c + ": " + R.fmt(v));
        R.pick(b, function () {
          cross(r, c, v);
        });
        cellEls.push({ r: r, c: c, el: b });
        td.appendChild(b);
        if (r !== c && (best === null || Math.abs(v) > Math.abs(best.v)))
          best = { r: r, c: c, v: v };
      }
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });

  function cross(r, c, v) {
    Object.keys(rowHeads).forEach(function (k) {
      rowHeads[k].classList.toggle("is-cross", k === r);
    });
    Object.keys(colHeads).forEach(function (k) {
      colHeads[k].classList.toggle("is-cross", k === c);
    });
    cellEls.forEach(function (x) {
      x.el.classList.toggle("is-cross", x.r === r || x.c === c);
      x.el.classList.toggle("is-sel", x.r === r && x.c === c);
    });
    strip.show(r + " × " + c, R.fmt(v));
  }

  var bar = R.el("span", { class: "heatbar", "aria-hidden": "true" });
  (diverging
    ? ["n4", "n3", "n2", "n1", "0", "p1", "p2", "p3", "p4"]
    : ["s1", "s2", "s3", "s4", "s5"]
  ).forEach(function (s) {
    bar.appendChild(R.el("i", { class: "h-" + s }));
  });
  var key = R.el("div", { class: "heatkey" }, [
    R.el("span", { text: R.fmt(diverging ? -span : lo) }),
    bar,
    R.el("span", { text: R.fmt(diverging ? span : hi) }),
  ]);

  host.appendChild(key);
  host.appendChild(
    R.el("div", { class: "wbox" }, [
      R.el("table", { class: "grid" }, [R.el("thead", {}, [head]), body]),
    ]),
  );
  host.appendChild(strip.el);
  if (best === null && cellEls.length)
    best = { r: cellEls[0].r, c: cellEls[0].c, v: values[cellEls[0].r + "\u0000" + cellEls[0].c] };
  if (best) cross(best.r, best.c, best.v);
};
