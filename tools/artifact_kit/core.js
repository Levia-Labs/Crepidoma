"use strict";
/* Artifact kit core: DOM helpers, inline marks, page header, section dispatch. Spec text only reaches the DOM through
   textContent and text nodes. */
var R = (function () {
  var NS = { svg: "http://www.w3.org/2000/svg" };
  var types = {};

  function make(ns, tag, attrs, kids) {
    var node = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (kid) {
      if (kid) node.appendChild(kid);
    });
    return node;
  }
  function el(tag, attrs, kids) {
    return make(null, tag, attrs, kids);
  }
  function svg(tag, attrs, kids) {
    return make(NS.svg, tag, attrs, kids);
  }

  /* Inline marks: **bold**, `code` and [label](https://url); other schemes stay plain text. */
  var MARKS = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https:\/\/[^\s)]+\))/;
  function mark(parent, text) {
    String(text)
      .split(MARKS)
      .forEach(function (part) {
        if (!part) return;
        var link = /^\[([^\]]+)\]\((https:\/\/[^\s)]+)\)$/.exec(part);
        if (part.length > 4 && part.slice(0, 2) === "**" && part.slice(-2) === "**") {
          parent.appendChild(el("strong", { text: part.slice(2, -2) }));
        } else if (part.length > 2 && part[0] === "`" && part.slice(-1) === "`") {
          parent.appendChild(el("code", { text: part.slice(1, -1) }));
        } else if (link) {
          parent.appendChild(
            el("a", { href: link[2], rel: "noopener", target: "_blank", text: link[1] }),
          );
        } else {
          parent.appendChild(document.createTextNode(part));
        }
      });
    return parent;
  }
  function text(tag, attrs, value) {
    return mark(el(tag, attrs), value);
  }

  /* Interface words follow the spec lang (en, pl); spec.ui overrides single keys. Unknown lang falls back to en. */
  var words = UIDICT.en;
  function t(key, vars) {
    return String(words[key] === undefined ? key : words[key]).replace(
      /\{(\w+)\}/g,
      function (m, name) {
        return vars && vars[name] !== undefined ? vars[name] : m;
      },
    );
  }
  function setLang(data) {
    var base =
      UIDICT[
        String(data.lang || "en")
          .slice(0, 2)
          .toLowerCase()
      ] || {};
    words = Object.assign({}, UIDICT.en, base, data.ui || {});
  }

  /* Notes never print inline: they show in a tooltip on hover, focus or tap. */
  var tipEl = null;
  function tip(target, content) {
    if (!content) return;
    if (!target.getAttribute("tabindex")) target.setAttribute("tabindex", "0");
    function show() {
      if (!tipEl) {
        tipEl = el("div", { class: "tip", role: "tooltip", hidden: "" });
        document.body.appendChild(tipEl);
        document.addEventListener("keydown", function (ev) {
          if (ev.key === "Escape") tipEl.hidden = true;
        });
      }
      tipEl.textContent = "";
      mark(tipEl, content);
      tipEl.hidden = false;
      var r = target.getBoundingClientRect();
      var left = Math.max(8, Math.min(r.left, window.innerWidth - tipEl.offsetWidth - 8));
      var below = r.bottom + 6;
      var top =
        below + tipEl.offsetHeight > window.innerHeight ? r.top - tipEl.offsetHeight - 6 : below;
      tipEl.style.left = left + "px";
      tipEl.style.top = Math.max(8, top) + "px";
    }
    function hide() {
      if (tipEl) tipEl.hidden = true;
    }
    ["mouseenter", "focus", "touchstart"].forEach(function (e) {
      target.addEventListener(e, show);
    });
    ["mouseleave", "blur"].forEach(function (e) {
      target.addEventListener(e, hide);
    });
  }

  /* Detail strip under a widget: show(title, body) replaces its content. */
  function strip() {
    var box = el("div", { class: "strip", "aria-live": "polite" });
    return {
      el: box,
      show: function (title, body) {
        box.textContent = "";
        box.appendChild(el("b", { text: title }));
        if (body) box.appendChild(text("span", {}, body));
      },
    };
  }

  function fmt(value) {
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  }

  /* Bind pointer, touch and keyboard selection: hover and focus select, click and Enter/Space too. */
  function pick(target, fn) {
    target.addEventListener("mouseenter", fn);
    target.addEventListener("focus", fn);
    target.addEventListener("click", fn);
    target.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        fn(ev);
      }
    });
  }

  function header(data) {
    var head = el("header");
    if (data.eyebrow) head.appendChild(el("div", { class: "eyebrow", text: data.eyebrow }));
    head.appendChild(el("h1", { text: data.title }));
    if (data.lede) head.appendChild(text("p", { class: "lede" }, data.lede));
    if (data.stats && data.stats.length) {
      var stats = el("div", { class: "stats" });
      data.stats.forEach(function (s) {
        stats.appendChild(
          el("div", { class: "stat" }, [el("b", { text: s.value }), el("span", { text: s.label })]),
        );
      });
      head.appendChild(stats);
    }
    return head;
  }

  function boot() {
    var data = JSON.parse(document.getElementById("artifact-data").textContent);
    setLang(data);
    var root = document.getElementById("app");
    root.appendChild(header(data));
    (data.sections || []).forEach(function (sec) {
      var host = el("section");
      if (sec.id) host.id = sec.id;
      if (sec.title) host.appendChild(el("h2", { text: sec.title }));
      if (sec.lede) host.appendChild(text("p", { class: "lede" }, sec.lede));
      if (types[sec.type]) types[sec.type](sec, host);
      root.appendChild(host);
    });
  }

  return {
    el: el,
    svg: svg,
    mark: mark,
    text: text,
    t: t,
    tip: tip,
    strip: strip,
    fmt: fmt,
    pick: pick,
    types: types,
    boot: boot,
  };
})();
