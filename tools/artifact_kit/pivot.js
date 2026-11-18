"use strict";
/* Pivot table over flat records: pick row and column fields, a measure and an aggregation. Cells are heat-shaded;
   a click lists the matching records. */
R.types.pivot = function (sec, host) {
  var AGGS = ["sum", "count", "avg", "min", "max"];
  var state = {
    rows: sec.rows || sec.dims[0],
    cols: sec.cols || sec.dims[1] || sec.dims[0],
    measure: sec.measure || sec.measures[0],
    agg: sec.agg || "sum",
  };
  var key = sec.id || "pivot";
  var table = R.el("div", { class: "wbox" });
  var strip = R.strip();
  var list = R.el("div", { class: "wbox" });

  function control(label, name, options, words) {
    var id = key + "-" + name;
    var select = R.el(
      "select",
      { id: id },
      options.map(function (o) {
        var opt = R.el("option", { value: o, text: words ? R.t(o) : o });
        if (o === state[name]) opt.setAttribute("selected", "");
        return opt;
      }),
    );
    select.addEventListener("change", function () {
      state[name] = select.value;
      draw();
    });
    return R.el("label", { for: id }, [document.createTextNode(label), select]);
  }

  /* dim values keep first-appearance order; all-numeric values sort numerically */
  function uniq(field) {
    var out = [];
    sec.records.forEach(function (r) {
      if (r[field] !== undefined && out.indexOf(String(r[field])) < 0) out.push(String(r[field]));
    });
    var numeric = out.every(function (v) {
      return v.trim() !== "" && !isNaN(Number(v));
    });
    return numeric
      ? out.sort(function (a, b) {
          return a - b;
        })
      : out;
  }
  function aggregate(rs) {
    if (!rs.length) return null;
    if (state.agg === "count") return rs.length;
    var v = rs.map(function (r) {
      return Number(r[state.measure]);
    });
    if (state.agg === "min") return Math.min.apply(null, v);
    if (state.agg === "max") return Math.max.apply(null, v);
    var sum = v.reduce(function (a, b) {
      return a + b;
    }, 0);
    return state.agg === "avg" ? sum / v.length : sum;
  }
  function matching(rv, cv) {
    return sec.records.filter(function (r) {
      return (
        (rv === null || String(r[state.rows]) === rv) &&
        (cv === null || String(r[state.cols]) === cv)
      );
    });
  }
  function level(v, lo, hi) {
    return hi === lo ? 3 : 1 + Math.round(((v - lo) / (hi - lo)) * 4);
  }
  function show(rv, cv, button) {
    Array.prototype.forEach.call(table.querySelectorAll(".cell.is-sel"), function (b) {
      b.classList.remove("is-sel");
    });
    button.classList.add("is-sel");
    var rs = matching(rv, cv);
    var what =
      state.agg === "count"
        ? R.t("count")
        : R.t("aggOf", { agg: R.t(state.agg), measure: state.measure });
    strip.show(rv + " × " + cv, what + ": " + R.fmt(aggregate(rs)));
    var fields = sec.dims.concat(sec.measures);
    var body = R.el("tbody");
    rs.slice(0, 12).forEach(function (r) {
      body.appendChild(
        R.el(
          "tr",
          {},
          fields.map(function (f, i) {
            return R.el("td", {
              class: i >= sec.dims.length ? "num" : "",
              text: r[f] === undefined ? "" : String(r[f]),
            });
          }),
        ),
      );
    });
    if (rs.length > 12)
      body.appendChild(
        R.el("tr", {}, [
          R.el("td", {
            class: "more",
            colspan: fields.length,
            text: R.t("more", { n: rs.length - 12 }),
          }),
        ]),
      );
    var head = R.el(
      "tr",
      {},
      fields.map(function (f) {
        return R.el("th", { text: f });
      }),
    );
    list.textContent = "";
    list.appendChild(R.el("table", { class: "grid recs" }, [R.el("thead", {}, [head]), body]));
  }

  function draw() {
    var rowsV = uniq(state.rows),
      colsV = uniq(state.cols);
    var values = [];
    var cells = rowsV.map(function (rv) {
      return colsV.map(function (cv) {
        var v = aggregate(matching(rv, cv));
        if (v !== null) values.push(v);
        return v;
      });
    });
    var lo = Math.min.apply(null, values),
      hi = Math.max.apply(null, values);
    var head = R.el("tr", {}, [R.el("th", { text: state.rows + " \\ " + state.cols })]);
    colsV.forEach(function (cv) {
      head.appendChild(R.el("th", { text: cv }));
    });
    head.appendChild(R.el("th", { text: R.t("total") }));
    var body = R.el("tbody");
    var best = null;
    rowsV.forEach(function (rv, ri) {
      var tr = R.el("tr", {}, [R.el("th", { text: rv })]);
      colsV.forEach(function (cv, ci) {
        var v = cells[ri][ci],
          td = R.el("td");
        if (v === null) {
          td.appendChild(R.el("span", { class: "cell empty", text: "·" }));
        } else {
          var lv = level(v, lo, hi);
          var b = R.el("button", {
            type: "button",
            class: "cell h-s" + lv + (lv >= 4 ? " hi" : ""),
            text: R.fmt(v),
          });
          b.addEventListener("click", function () {
            show(rv, cv, b);
          });
          td.appendChild(b);
          if (best === null || v > best.v) best = { v: v, rv: rv, cv: cv, b: b };
        }
        tr.appendChild(td);
      });
      tr.appendChild(R.el("td", { class: "tot", text: R.fmt(aggregate(matching(rv, null))) }));
      body.appendChild(tr);
    });
    var foot = R.el("tr", {}, [R.el("th", { text: R.t("total") })]);
    colsV.forEach(function (cv) {
      foot.appendChild(R.el("td", { class: "tot", text: R.fmt(aggregate(matching(null, cv))) }));
    });
    foot.appendChild(R.el("td", { class: "tot", text: R.fmt(aggregate(sec.records)) }));
    body.appendChild(foot);
    table.textContent = "";
    table.appendChild(R.el("table", { class: "grid" }, [R.el("thead", {}, [head]), body]));
    if (best) show(best.rv, best.cv, best.b);
  }

  host.appendChild(
    R.el("div", { class: "controls" }, [
      control(R.t("rows"), "rows", sec.dims),
      control(R.t("cols"), "cols", sec.dims),
      control(R.t("measure"), "measure", sec.measures),
      control(R.t("aggregate"), "agg", AGGS, true),
    ]),
  );
  host.appendChild(table);
  host.appendChild(strip.el);
  host.appendChild(list);
  draw();
};
