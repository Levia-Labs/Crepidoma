"use strict";
/* Stacked layers of blocks with links between blocks of any layers. Selecting a block lights its links. */
R.types.layers = function (sec, host) {
  var BH = 38,
    GX = 14,
    GY = 12,
    LABEL = 150,
    PADX = 12,
    PADT = 26,
    PADB = 12,
    MAXW = 1040;
  var layers = sec.layers,
    blocks = {},
    linked = {},
    linkEls = [],
    blockEls = {};

  /* word-wrap into at most `max` lines of `chars`; the flag says text was cut */
  function wrap(label, chars, max) {
    var lines = [],
      line = "",
      cut = false;
    label.split(/\s+/).forEach(function (word) {
      if (line && (line + " " + word).length > chars) {
        lines.push(line);
        line = word;
      } else {
        line = line ? line + " " + word : word;
      }
    });
    lines.push(line);
    if (lines.length > max) {
      lines = lines.slice(0, max);
      cut = true;
    }
    lines = lines.map(function (l, i) {
      if (l.length > chars) {
        cut = true;
        return l.slice(0, chars - 1) + "…";
      }
      return i === max - 1 && cut ? l.replace(/.?$/, "…") : l;
    });
    return { lines: lines, cut: cut };
  }

  var longest = 0,
    widest = 1;
  layers.forEach(function (l) {
    widest = Math.max(widest, l.blocks.length);
    l.blocks.forEach(function (b) {
      longest = Math.max(longest, b.label.length);
    });
  });
  var BW = Math.min(220, Math.max(120, longest * 7 + 24));
  var perRow = Math.max(1, Math.min(widest, Math.floor((MAXW - LABEL) / (BW + GX))));
  var width = LABEL + PADX * 2 + perRow * (BW + GX);
  var top = 0,
    tops = [];
  var s = R.svg("svg", { class: "g" });
  s.style.width = "100%";
  s.style.minWidth = width + "px";

  layers.forEach(function (layer, li) {
    var rows = Math.ceil(layer.blocks.length / perRow);
    var h = PADT + rows * (BH + GY) - GY + PADB;
    tops[li] = top;
    s.appendChild(
      R.svg("rect", {
        class: "lane" + (li % 2 ? " odd" : ""),
        x: 0,
        y: top,
        width: "100%",
        height: h,
      }),
    );
    var name = wrap(layer.label, Math.floor((LABEL - PADX - 6) / 9), 3).lines;
    name.forEach(function (line, i) {
      var y = top + h / 2 + 4 + (i - (name.length - 1) / 2) * 15;
      s.appendChild(R.svg("text", { class: "lanehead", x: PADX, y: y, text: line }));
    });
    layer.blocks.forEach(function (b, bi) {
      b.x = LABEL + PADX + (bi % perRow) * (BW + GX);
      b.y = top + PADT + Math.floor(bi / perRow) * (BH + GY);
      b.layer = li;
      blocks[b.id] = b;
      linked[b.id] = [];
    });
    top += h;
  });
  s.setAttribute("height", top);
  s.style.height = top + "px";
  (sec.links || []).forEach(function (l) {
    linked[l[0]].push(l[1]);
    linked[l[1]].push(l[0]);
    var a = blocks[l[0]],
      b = blocks[l[1]];
    /* the higher block links from its bottom edge, the lower from its top edge; blocks in one row arc over the top
       inside the layer padding */
    var ax = a.x + BW / 2,
      bx = b.x + BW / 2,
      d;
    if (a.y === b.y) {
      var rise = Math.min(24, 10 + Math.abs(bx - ax) / 40);
      d =
        "M" +
        ax +
        " " +
        a.y +
        "C" +
        ax +
        " " +
        (a.y - rise) +
        " " +
        bx +
        " " +
        (a.y - rise) +
        " " +
        bx +
        " " +
        a.y;
    } else {
      var ay = a.y < b.y ? a.y + BH : a.y,
        by = b.y < a.y ? b.y + BH : b.y,
        bend = (by - ay) / 2;
      d =
        "M" +
        ax +
        " " +
        ay +
        "C" +
        ax +
        " " +
        (ay + bend) +
        " " +
        bx +
        " " +
        (by - bend) +
        " " +
        bx +
        " " +
        by;
    }
    var end = R.svg("circle", {
      class: "lend",
      r: 3.5,
      cx: bx,
      cy: a.y === b.y ? b.y : b.y < a.y ? b.y + BH : b.y,
    });
    var path = R.svg("path", { class: "lnk", d: d });
    s.appendChild(path);
    linkEls.push({ from: l[0], to: l[1], path: path, end: end });
  });
  linkEls.forEach(function (l) {
    l.end.style.display = "none";
    s.appendChild(l.end);
  });
  layers.forEach(function (layer) {
    layer.blocks.forEach(function (b) {
      var text = wrap(b.label, Math.floor((BW - 16) / 7), 2);
      var g = R.svg(
        "g",
        {
          class: "blk t-" + (b.tone || "neutral"),
          transform: "translate(" + b.x + " " + b.y + ")",
          tabindex: "0",
          role: "button",
          "aria-label": b.label,
        },
        [R.svg("rect", { width: BW, height: BH, rx: 3 })],
      );
      text.lines.forEach(function (line, i) {
        var y = BH / 2 + 4.5 + (i - (text.lines.length - 1) / 2) * 13;
        g.appendChild(R.svg("text", { x: 8, y: y, text: line }));
      });
      g.appendChild(R.svg("title", { text: b.label }));
      if (text.cut) R.tip(g, b.label);
      R.pick(g, function () {
        select(b.id);
      });
      blockEls[b.id] = g;
      s.appendChild(g);
    });
  });

  var strip = R.strip();
  function select(id) {
    var b = blocks[id];
    var near = {};
    linked[id].forEach(function (n) {
      near[n] = true;
    });
    s.classList.add("has-sel");
    Object.keys(blockEls).forEach(function (k) {
      var c = blockEls[k].classList;
      c.toggle("is-sel", k === id);
      c.toggle("is-link", !!near[k]);
      c.toggle("is-dim", k !== id && !near[k]);
    });
    linkEls.forEach(function (l) {
      var on = l.from === id || l.to === id;
      l.path.classList.toggle("is-on", on);
      l.end.style.display = on ? "" : "none";
    });
    var names = linked[id].map(function (n) {
      return blocks[n].label;
    });
    var linkedTo = names.length ? R.t("linked", { names: names.join(", ") }) : R.t("noLinks");
    var body = [b.note, linkedTo].filter(Boolean).join(" · ");
    strip.show(b.label, body);
  }

  host.appendChild(R.el("div", { class: "wbox" }, [s]));
  host.appendChild(strip.el);
  var first = (sec.links && sec.links.length && sec.links[0][0]) || layers[0].blocks[0].id;
  select(first);
};
