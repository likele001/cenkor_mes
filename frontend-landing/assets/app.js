// 扩展清单：分类过滤 + 关键词搜索（纯静态，无依赖）
(function () {
  var search = document.getElementById('extSearch');
  var filters = document.getElementById('extFilters');
  var empty = document.getElementById('extEmpty');
  if (!search || !filters) return;

  var groups = Array.prototype.slice.call(document.querySelectorAll('.ext-group'));
  var activeCat = 'all';

  function apply() {
    var q = (search.value || '').trim().toLowerCase();
    var visible = 0;

    groups.forEach(function (group) {
      var catMatch = activeCat === 'all' || group.dataset.cat === activeCat;
      var items = group.querySelectorAll('.ext-item');
      var groupVisible = 0;

      items.forEach(function (item) {
        var hit = !q || item.textContent.toLowerCase().indexOf(q) !== -1;
        var show = catMatch && hit;
        item.style.display = show ? '' : 'none';
        if (show) groupVisible++;
      });

      group.style.display = groupVisible > 0 ? '' : 'none';
      visible += groupVisible;
    });

    if (empty) empty.style.display = visible === 0 ? 'block' : 'none';
  }

  filters.addEventListener('click', function (e) {
    var btn = e.target.closest('.filter-btn');
    if (!btn) return;
    Array.prototype.forEach.call(filters.querySelectorAll('.filter-btn'), function (b) {
      b.classList.toggle('on', b === btn);
    });
    activeCat = btn.dataset.cat;
    apply();
  });

  search.addEventListener('input', apply);

  // 支持从首页带查询参数跳转：/extensions.html?q=AI
  var params = new URLSearchParams(window.location.search);
  if (params.get('q')) {
    search.value = params.get('q');
    apply();
  }
})();
