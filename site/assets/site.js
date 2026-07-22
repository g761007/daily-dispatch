// DailyDispatch — 原生 JavaScript，無外部服務、無外部 CDN 依賴。

(function () {
  "use strict";

  function setupArchiveSearch() {
    var input = document.getElementById("archive-search-input");
    if (!input) return; // 非歷史摘要頁，不需要搜尋功能

    var items = Array.prototype.slice.call(document.querySelectorAll(".archive-item"));
    var groups = Array.prototype.slice.call(document.querySelectorAll(".archive-group"));
    var groupTitles = Array.prototype.slice.call(document.querySelectorAll(".archive-group-title"));
    var emptyState = document.getElementById("archive-search-empty");

    function normalize(text) {
      return (text || "").toLowerCase();
    }

    function applyFilter() {
      var query = normalize(input.value.trim());
      var totalVisible = 0;

      items.forEach(function (item) {
        var haystack = normalize(item.getAttribute("data-search"));
        var matches = query === "" || haystack.indexOf(query) !== -1;
        item.hidden = !matches;
        if (matches) totalVisible += 1;
      });

      groups.forEach(function (group, index) {
        var visibleInGroup = group.querySelectorAll(".archive-item:not([hidden])").length;
        var isEmpty = visibleInGroup === 0;
        group.hidden = isEmpty;
        if (groupTitles[index]) {
          groupTitles[index].hidden = isEmpty;
        }
      });

      if (emptyState) {
        emptyState.hidden = totalVisible !== 0;
      }
    }

    input.addEventListener("input", applyFilter);
    applyFilter();
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupArchiveSearch();
  });
})();
