/* ============================================================
   main.js
   Comportamientos globales: auto-cierre de mensajes flash.
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  var messages = document.querySelectorAll('.flash-message');
  messages.forEach(function (msg) {
    setTimeout(function () {
      msg.style.transition = 'opacity 0.4s ease';
      msg.style.opacity = '0';
      setTimeout(function () { msg.remove(); }, 400);
    }, 6000);
  });
});
