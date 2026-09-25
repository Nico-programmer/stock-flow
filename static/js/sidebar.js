/* ============================================================
   sidebar.js
   Rotación del chevron en submenús y sincronía con Bootstrap Collapse.
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  var toggles = document.querySelectorAll('[data-sidebar-toggle]');
  toggles.forEach(function (toggle) {
    var targetSelector = toggle.getAttribute('data-bs-target');
    var target = document.querySelector(targetSelector);
    if (!target) return;

    target.addEventListener('shown.bs.collapse', function () {
      toggle.setAttribute('aria-expanded', 'true');
    });
    target.addEventListener('hidden.bs.collapse', function () {
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
});
