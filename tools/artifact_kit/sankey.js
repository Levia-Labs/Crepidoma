"use strict";
/* Sankey: nodes in stage columns, height by throughput, flows as bands. Hovering a node or a flow lights the
   paths connected to it. */
R.types.sankey = function (sec, host) {
  var NW = 14,
    COLW = 190,
    PAD = 16,
    GAP = 14,
    LABEL = 120,
    H = 360;
  var byId = Object.create(null),
    outs = Object.create(null),
    ins = Object.create(null);
  sec.nodes.forEach(function (n) {
    byId[n.id] = n;
    outs[n.id] = [];
    ins[n.id] = [];
  });
  var flows = sec.flows.map(function (f, i) {
    var flow = { i: i, from: f[0], to: f[1], value: f[2] };
    outs[f[0]].push(flow);
    ins[f[1]].push(flow);
    return flow;
  });

  var memo = Object.create(null);
  function depth(id) {
    if (memo[id] === undefined) {
      memo[id] = ins[id].reduce(function (m, f) {
        return Math.max(m, depth(f.from) + 1);
      }, 0);
    }
    return memo[id];
  }
  function sum(list) {
    return list.reduce(function (s, f) {
      return s + f.value;
    }, 0);
  }
  var stages = [];
  sec.nodes.forEach(function (n, i) {
    n.stage = typeof n.stage === "number" ? n.stage : depth(n.id);
    n.through = Math.max(sum(ins[n.id]), sum(outs[n.id]));
    n.order = i;
    (stages[n.stage] = stages[n.stage] || []).push(n);
  });
  stages = stages.map(function (c) {
    return c || [];
  });
  var k = Infinity;
  stages.forEach(function (col) {
    var t = sum(
      col.map(function (n) {
        return { value: n.through };
      }),
    );
    if (t > 0) k = Math.min(k, (H - (col.length - 1) * GAP) / t);
  });
  if (!isFinite(k)) k = 1;
  var width = PAD * 2 + stages.length * COLW + LABEL;
  stages.forEach(function (col, ci) {
    var y = PAD;
    col.forEach(function (n) {
      n.x = PAD + ci * COLW;
      n.y = y;
      n.h = Math.max(4, n.through * k);
      y += n.h + GAP;
    });
  });

  /* stack band ends along each node, ordered by the other end's height so bands do not cross needlessly */
  sec.nodes.forEach(function (n) {
    var oy = n.y,
      iy = n.y;
    outs[n.id]
      .sort(function (a, b) {
        return byId[a.to].y - byId[b.to].y;
      })
      .forEach(function (f) {
        f.w = Math.max(2, f.value * k);
        f.y0 = oy + f.w / 2;
        oy += f.w;
      });
    ins[n.id]
      .sort(function (a, b) {
        return byId[a.from].y - byId[b.from].y;
      })
      .forEach(function (f) {
        f.w = Math.max(2, f.value * k);
        f.y1 = iy + f.w / 2;
        iy += f.w;
      });
  });

  var s = R.svg("svg", {
    class: "g",
    viewBox: "0 0 " + width + " " + (H + PAD * 2 + 40),
    width: width,
    height: H + PAD * 2 + 40,
  });
  s.style.width = width + "px";
  var strip = R.strip();
  var flowEls = [],
    nodeEls = Object.create(null);

  flows.forEach(function (f) {
    var a = byId[f.from],
      b = byId[f.to];
    var x0 = a.x + NW,
      x1 = b.x,
      mid = (x0 + x1) / 2;
    var p = R.svg("path", {
      class: "flow c" + ((a.order % 8) + 1),
      d:
        "M" +
        x0 +
        " " +
        f.y0 +
        "C" +
        mid +
        " " +
        f.y0 +
        " " +
        mid +
        " " +
        f.y1 +
        " " +
        x1 +
        " " +
        f.y1,
      "stroke-width": f.w,
      tabindex: "0",
      role: "button",
      "aria-label": R.t("flowAria", { from: a.label, to: b.label, value: R.fmt(f.value) }),
    });
    R.pick(p, function () {
      light([f], [a.id, b.id]);
      p.classList.add("is-on");
      strip.show(
        a.label + " → " + b.label,
        R.t("shareOf", {
          value: R.fmt(f.value),
          pct: a.through ? Math.round((f.value / a.through) * 100) : 0,
          name: a.label,
        }),
      );
    });
    f.el = p;
    flowEls.push(p);
    s.appendChild(p);
  });

  sec.nodes.forEach(function (n) {
    var g = R.svg(
      "g",
      {
        class: "snode c" + ((n.order % 8) + 1),
        tabindex: "0",
        role: "button",
        "aria-label": n.label,
      },
      [R.svg("rect", { x: n.x, y: n.y, width: NW, height: n.h })],
    );
    var last = n.stage === stages.length - 1;
    g.appendChild(
      R.svg("text", {
        x: last ? n.x - 6 : n.x + NW + 6,
        y: n.y + n.h / 2 + 4,
        "text-anchor": last ? "end" : "start",
        text: n.label,
      }),
    );
    R.pick(g, function () {
      select(n);
    });
    nodeEls[n.id] = g;
    s.appendChild(g);
  });

  function walk(id, map, field, seen) {
    map[id].forEach(function (f) {
      if (!seen[f.i]) {
        seen[f.i] = f;
        walk(f[field], map, field, seen);
      }
    });
  }
  function light(list, ids) {
    s.classList.add("has-sel");
    flowEls.forEach(function (el) {
      el.classList.remove("is-on");
    });
    list.forEach(function (f) {
      f.el.classList.add("is-on");
    });
    var on = Object.create(null);
    ids.forEach(function (id) {
      on[id] = true;
    });
    list.forEach(function (f) {
      on[f.from] = true;
      on[f.to] = true;
    });
    Object.keys(nodeEls).forEach(function (id) {
      nodeEls[id].classList.toggle("is-dim", !on[id]);
      nodeEls[id].classList.toggle("is-sel", ids.length === 1 && ids[0] === id);
    });
  }
  function select(n) {
    var seen = Object.create(null);
    walk(n.id, outs, "to", seen);
    walk(n.id, ins, "from", seen);
    light(
      Object.keys(seen).map(function (i) {
        return seen[i];
      }),
      [n.id],
    );
    strip.show(
      n.label,
      R.t("flowThrough", {
        in: R.fmt(sum(ins[n.id])),
        out: R.fmt(sum(outs[n.id])),
        stage: n.stage + 1,
      }),
    );
  }

  host.appendChild(R.el("div", { class: "wbox" }, [s]));
  host.appendChild(strip.el);
  select(
    sec.nodes.slice().sort(function (a, b) {
      return b.through - a.through;
    })[0],
  );
};
