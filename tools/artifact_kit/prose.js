"use strict";
R.types.prose = function (sec, host) {
  var box = R.el("div", { class: "prose" });
  (sec.paragraphs || []).forEach(function (p) {
    box.appendChild(R.text("p", {}, p));
  });
  host.appendChild(box);
};
