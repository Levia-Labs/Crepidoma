"use strict";
R.types.cards = function (sec, host) {
  var grid = R.el("div", { class: "cards" });
  (sec.items || []).forEach(function (item) {
    var card = R.el("article", { class: "card t-" + (item.tone || "neutral") });
    if (item.tag) card.appendChild(R.el("span", { class: "tag", text: item.tag }));
    card.appendChild(R.el("h3", { text: item.title }));
    if (item.body) card.appendChild(R.text("p", {}, item.body));
    grid.appendChild(card);
  });
  host.appendChild(grid);
};
