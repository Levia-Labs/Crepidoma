"use strict";
/* Dependency graph: hand-written SVG, columns by longest-path depth unless a node names its column, optional lane
   bands. An edge [a, b] means a is a prerequisite of b. */
R.types.graph = function (sec, host) {
  var H = 34,
    GX = 64,
    GY = 12,
    PAD = 16,
    HEAD = 26,
    LANEHEAD = 22;
  var byId = Object.create(null),
    preds = Object.create(null),
    succs = Object.create(null),
    nodeEls = Object.create(null),
    edgeEls = [];
  var mode = sec.mode === "chain" ? "chain" : "direct";
  var lanes = sec.lanes || [];
  var columns = sec.columns || [];
  var cats = Object.create(null);
  (sec.categories || []).forEach(function (c, i) {
    cats[c.id] = { label: c.label, cls: "c" + (i < 8 ? i + 1 : 8) };
  });
  sec.nodes.forEach(function (n) {
    byId[n.id] = n;
    preds[n.id] = [];
    succs[n.id] = [];
  });
  (sec.edges || []).forEach(function (e) {
    preds[e[1]].push(e[0]);
    succs[e[0]].push(e[1]);
  });

  var depthMemo = Object.create(null);
  function depth(id) {
    if (depthMemo[id] === undefined) {
      depthMemo[id] = preds[id].reduce(function (m, p) {
        return Math.max(m, depth(p) + 1);
      }, 0);
    }
    return depthMemo[id];
  }
  function colOf(n) {
    return typeof n.column === "number" ? n.column : depth(n.id);
  }

  var W = sec.nodes.reduce(function (m, n) {
    return Math.max(m, Math.min(220, n.label.length * 7 + 28));
  }, 120);
  var maxChars = Math.floor((W - 28) / 7);
  var ncols = Math.max(columns.length, 1 + Math.max.apply(null, sec.nodes.map(colOf)));
  var nlanes = lanes.length || 1;

  var stack = Object.create(null),
    rows = [];
  sec.nodes.forEach(function (n) {
    var lane = lanes.length ? n.lane || 0 : 0;
    var key = lane + ":" + colOf(n);
    stack[key] = (stack[key] || 0) + 1;
    n.row = stack[key] - 1;
    n.laneIx = lane;
    rows[lane] = Math.max(rows[lane] || 1, stack[key]);
  });
  var top = [],
    y = columns.length ? HEAD : 0;
  for (var l = 0; l < nlanes; l++) {
    top[l] = y;
    y += (lanes.length ? LANEHEAD : 0) + (rows[l] || 1) * (H + GY) + (lanes.length ? 8 : 0);
  }
  var width = PAD * 2 + ncols * W + (ncols - 1) * GX;
  var height = y + PAD;
  sec.nodes.forEach(function (n) {
    n.x = PAD + colOf(n) * (W + GX);
    n.y =
      top[n.laneIx] +
      (lanes.length ? LANEHEAD : 0) +
      (n.row + (rows[n.laneIx] - stack[n.laneIx + ":" + colOf(n)]) / 2) * (H + GY) +
      (lanes.length ? 0 : PAD / 2);
  });

  var s = R.svg("svg", {
    class: "g",
    viewBox: "0 0 " + width + " " + height,
    width: width,
    height: height,
  });
  s.style.minWidth = s.style.maxWidth = width + "px";
  s.style.width = "100%";
  s.style.height = "auto";
  lanes.forEach(function (name, i) {
    var h = (rows[i] || 1) * (H + GY) + LANEHEAD + 8;
    s.appendChild(
      R.svg("rect", {
        class: "lane" + (i % 2 ? " odd" : ""),
        x: 0,
        y: top[i],
        width: width,
        height: h,
      }),
    );
    s.appendChild(R.svg("text", { class: "lanehead", x: PAD, y: top[i] + 15, text: name }));
  });
  columns.forEach(function (name, i) {
    s.appendChild(R.svg("text", { class: "colhead", x: PAD + i * (W + GX), y: 16, text: name }));
  });
  (sec.edges || []).forEach(function (e) {
    var a = byId[e[0]],
      b = byId[e[1]];
    var x1 = a.x + W,
      y1 = a.y + H / 2,
      x2 = b.x,
      y2 = b.y + H / 2;
    var dx = Math.max(30, Math.abs(x2 - x1) / 2);
    var path = R.svg("path", {
      class: "edge",
      d:
        "M" +
        x1 +
        " " +
        y1 +
        "C" +
        (x1 + dx) +
        " " +
        y1 +
        " " +
        (x2 - dx) +
        " " +
        y2 +
        " " +
        x2 +
        " " +
        y2,
    });
    s.appendChild(path);
    edgeEls.push({ from: e[0], to: e[1], el: path });
  });
  sec.nodes.forEach(function (n) {
    var cat = cats[n.category] || { label: n.category, cls: "c1" };
    var label = n.label.length > maxChars ? n.label.slice(0, maxChars - 1) + "…" : n.label;
    var g = R.svg(
      "g",
      {
        class: "node " + cat.cls,
        transform: "translate(" + n.x + " " + n.y + ")",
        tabindex: "0",
        role: "button",
        "aria-label": n.label + (n.flag === "fix" ? ", " + R.t("needsFix") : ""),
      },
      [
        R.svg("title", { text: n.label }),
        R.svg("rect", { class: "box", width: W, height: H, rx: 3 }),
        R.svg("rect", { class: "stripe", width: 5, height: H, rx: 2 }),
        R.svg("text", { x: 14, y: H / 2 + 4.5, text: label }),
      ],
    );
    if (n.flag === "fix") g.appendChild(R.svg("circle", { cx: W - 10, cy: 10, r: 4.5 }));
    R.tip(g, n.note);
    g.addEventListener("click", function () {
      select(n.id);
    });
    g.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        select(n.id);
      }
    });
    nodeEls[n.id] = g;
    s.appendChild(g);
  });

  function walk(id, map, closure) {
    var seen = Object.create(null),
      queue = map[id].slice();
    while (queue.length) {
      var next = queue.shift();
      if (seen[next]) continue;
      seen[next] = true;
      if (closure) queue = queue.concat(map[next]);
    }
    return seen;
  }

  var panel = R.el("aside", { class: "panel", "aria-live": "polite" });
  var selected = null;
  function chips(ids, cls) {
    var box = R.el("div", { class: "chips" });
    ids.forEach(function (id) {
      var chip = R.el("button", { type: "button", class: "chip " + cls, text: byId[id].label });
      chip.addEventListener("click", function () {
        select(id);
        nodeEls[id].focus();
      });
      box.appendChild(chip);
    });
    if (!ids.length) box.appendChild(R.el("span", { class: "none", text: R.t("none") }));
    return box;
  }
  function block(title, body) {
    return R.el("div", { class: "block" }, [R.el("h4", { text: title }), body]);
  }
  function renderPanel(n) {
    panel.textContent = "";
    if (!n) {
      panel.appendChild(R.el("p", { class: "none", text: R.t("selectNode") }));
      return;
    }
    var cat = cats[n.category] || { label: n.category, cls: "c1" };
    panel.appendChild(
      R.el("div", { class: "head " + cat.cls }, [
        R.el("div", { class: "eyebrow", text: cat.label }),
        R.el("h3", { text: n.label }),
      ]),
    );
    if (n.note) panel.appendChild(R.text("p", {}, n.note));
    if (n.flag === "fix") panel.appendChild(R.el("p", { class: "fixnote", text: R.t("needsFix") }));
    (n.facts || []).forEach(function (fact) {
      var list = R.el("ul");
      fact.items.forEach(function (item) {
        list.appendChild(R.text("li", {}, item));
      });
      panel.appendChild(block(fact.label, list));
    });
    panel.appendChild(block(R.t("requires"), chips(preds[n.id], "in")));
    panel.appendChild(block(R.t("unlocks"), chips(succs[n.id], "out")));
  }

  function select(id) {
    if (!byId[id]) return;
    selected = id;
    var up = walk(id, preds, mode === "chain");
    var down = walk(id, succs, mode === "chain");
    s.classList.add("has-sel");
    sec.nodes.forEach(function (n) {
      var c = nodeEls[n.id].classList;
      c.toggle("is-sel", n.id === id);
      c.toggle("is-up", !!up[n.id]);
      c.toggle("is-down", !!down[n.id]);
      c.toggle("is-dim", n.id !== id && !up[n.id] && !down[n.id]);
    });
    edgeEls.forEach(function (e) {
      e.el.classList.toggle("is-up", (e.to === id || !!up[e.to]) && !!up[e.from]);
      e.el.classList.toggle("is-down", (e.from === id || !!down[e.from]) && !!down[e.to]);
    });
    renderPanel(byId[id]);
  }

  var seg = R.el("div", { class: "seg", role: "group", "aria-label": R.t("highlight") });
  [
    ["direct", R.t("direct")],
    ["chain", R.t("chain")],
  ].forEach(function (pair) {
    var b = R.el("button", {
      type: "button",
      "aria-pressed": String(mode === pair[0]),
      text: pair[1],
    });
    b.addEventListener("click", function () {
      mode = pair[0];
      Array.prototype.forEach.call(seg.children, function (other) {
        other.setAttribute("aria-pressed", String(other === b));
      });
      if (selected) select(selected);
    });
    seg.appendChild(b);
  });
  var legend = R.el("div", { class: "legend" });
  (sec.categories || []).forEach(function (c) {
    legend.appendChild(
      R.el("span", { class: cats[c.id].cls }, [
        R.el("i", { class: "sw" }),
        document.createTextNode(c.label),
      ]),
    );
  });
  legend.appendChild(
    R.el("span", {}, [R.el("i", { class: "ln up" }), document.createTextNode(R.t("requires"))]),
  );
  legend.appendChild(
    R.el("span", {}, [R.el("i", { class: "ln down" }), document.createTextNode(R.t("unlocks"))]),
  );
  if (
    sec.nodes.some(function (n) {
      return n.flag === "fix";
    })
  ) {
    legend.appendChild(
      R.el("span", {}, [R.el("i", { class: "dot" }), document.createTextNode(R.t("needsFix"))]),
    );
  }

  var box = R.el("div", { class: "graphbox" }, [
    R.el("div", { class: "graphbar" }, [legend, seg]),
    R.el("div", { class: "scroll" }, [s]),
  ]);
  host.appendChild(R.el("div", { class: "stage" }, [box, panel]));
  renderPanel(null);
  R.select = select;
  if (sec.start) select(sec.start);
};
