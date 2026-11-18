"use strict";
/* Squarified treemap: values sum upward, a click zooms into a block, the breadcrumb climbs back. */
R.types.treemap = function (sec, host) {
  var narrow = window.innerWidth < 600;
  var W = narrow ? 420 : 960,
    H = narrow ? 520 : 420,
    MIN_W = 64,
    MIN_H = 28;

  function total(n) {
    if (n.total === undefined) {
      n.total =
        n.children && n.children.length
          ? n.children.reduce(function (s, k) {
              return s + total(k);
            }, 0)
          : n.value || 0;
    }
    return n.total;
  }

  /* Bruls squarify: place sorted items in rows along the shorter side while the worst aspect ratio improves. */
  function squarify(items, x, y, w, h) {
    var out = [];
    var sum = items.reduce(function (s, i) {
      return s + i.total;
    }, 0);
    var scale = (w * h) / sum;
    var queue = items.slice();
    function worst(row, side) {
      var areas = row.map(function (i) {
        return i.total * scale;
      });
      var s = areas.reduce(function (a, b) {
        return a + b;
      }, 0);
      return Math.max(
        (side * side * Math.max.apply(null, areas)) / (s * s),
        (s * s) / (side * side * Math.min.apply(null, areas)),
      );
    }
    while (queue.length) {
      var side = Math.min(w, h),
        row = [queue.shift()];
      while (queue.length && worst(row.concat([queue[0]]), side) <= worst(row, side))
        row.push(queue.shift());
      var area = row.reduce(function (s, i) {
        return s + i.total * scale;
      }, 0);
      var thick = area / side,
        offset = 0;
      row.forEach(function (i) {
        var len = (i.total * scale) / thick;
        if (w >= h) out.push({ n: i, x: x, y: y + offset, w: thick, h: len });
        else out.push({ n: i, x: x + offset, y: y, w: len, h: thick });
        offset += len;
      });
      if (w >= h) {
        x += thick;
        w -= thick;
      } else {
        y += thick;
        h -= thick;
      }
    }
    return out;
  }

  var path = [sec.tree];
  var crumbs = R.el("div", { class: "crumbs" });
  var box = R.el("div", { class: "wbox" });
  var strip = R.strip();
  total(sec.tree);

  function describe(n, base) {
    var share = base ? Math.round((n.total / base.total) * 1000) / 10 : 100;
    var note = R.t("shareOf", {
      value: R.fmt(n.total),
      pct: share,
      name: base ? base.label : R.t("wholeWord"),
    });
    strip.show(n.label, [note, n.note].filter(Boolean).join(" · "));
  }

  function draw() {
    var cur = path[path.length - 1];
    crumbs.textContent = "";
    path.forEach(function (n, i) {
      var b = R.el("button", { type: "button", text: n.label });
      if (i === path.length - 1) b.setAttribute("aria-current", "true");
      b.addEventListener("click", function () {
        path = path.slice(0, i + 1);
        draw();
      });
      crumbs.appendChild(b);
    });
    var kids = (cur.children && cur.children.length ? cur.children : [cur]).filter(function (k) {
      return total(k) > 0;
    });
    kids.sort(function (a, b) {
      return b.total - a.total;
    });
    var s = R.svg("svg", { class: "g", height: H });
    s.style.width = "100%";
    s.style.height = H + "px";
    s.style.minWidth = narrow ? "0" : "560px";
    function pct(v) {
      return (v / W) * 100 + "%";
    }
    squarify(kids, 0, 0, W, H).forEach(function (r, i) {
      var n = r.n;
      var tone = n.tone || cur.tone || "c" + ((i % 8) + 1);
      /* a nested svg clips its label to the block; the width scales with the box, the height stays capped */
      var g = R.svg(
        "svg",
        {
          class: "tmb t-" + tone,
          x: pct(r.x),
          y: r.y,
          width: pct(r.w),
          height: r.h,
          tabindex: "0",
          role: "button",
          "aria-label": n.label,
        },
        [R.svg("rect", { width: "100%", height: "100%" })],
      );
      if (r.w >= MIN_W && r.h >= MIN_H)
        g.appendChild(R.svg("text", { x: 8, y: 19, text: n.label }));
      function enter() {
        Array.prototype.forEach.call(s.children, function (o) {
          o.classList.toggle("is-sel", o === g);
        });
        describe(n, cur);
      }
      R.pick(g, function (ev) {
        enter();
        if (
          ev &&
          ev.type !== "mouseenter" &&
          ev.type !== "focus" &&
          n.children &&
          n.children.length &&
          cur !== n
        ) {
          path.push(n);
          n.tone = n.tone || tone;
          draw();
        }
      });
      s.appendChild(g);
    });
    box.textContent = "";
    box.appendChild(s);
    describe(cur, path.length > 1 ? path[path.length - 2] : null);
  }

  host.appendChild(crumbs);
  host.appendChild(box);
  host.appendChild(strip.el);
  draw();
};
