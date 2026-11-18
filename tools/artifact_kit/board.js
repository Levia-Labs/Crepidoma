"use strict";
R.types.board = function (sec, host) {
  var byId = {};
  var legend = R.el("div", { class: "statuses" });
  (sec.statuses || []).forEach(function (s) {
    byId[s.id] = s;
    legend.appendChild(R.el("span", { class: "st t-" + s.tone, text: s.label }));
  });
  if (legend.childNodes.length) host.appendChild(legend);

  (sec.bands || []).forEach(function (band) {
    var box = R.el("div", { class: "band t-" + band.tone });
    var head = R.el("header", {}, [R.el("h3", { text: band.title })]);
    if (band.lede) head.appendChild(R.text("p", {}, band.lede));
    box.appendChild(head);
    var groups = R.el("div", { class: "groups" });
    (band.groups || []).forEach(function (group) {
      var heading = R.el("h4", { text: group.title });
      R.tip(heading, group.note);
      var card = R.el("div", { class: "group" }, [heading]);
      var list = R.el("ul", { class: "items" });
      (group.items || []).forEach(function (item) {
        var row = R.el("li", { class: "item" }, [R.text("span", {}, item.title)]);
        if (item.id) row.setAttribute("data-id", item.id);
        var status = byId[item.status];
        if (status)
          row.appendChild(R.el("span", { class: "st t-" + status.tone, text: status.label }));
        R.tip(row, item.note);
        list.appendChild(row);
      });
      card.appendChild(list);
      groups.appendChild(card);
    });
    box.appendChild(groups);
    host.appendChild(box);
  });
};
