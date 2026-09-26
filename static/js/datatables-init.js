/* ============================================================
   datatables-init.js
   Inicializa DataTables (búsqueda, orden, paginación) en toda
   tabla marcada con class="js-datatable". Columnas con class="nosort"
   quedan fuera del orden/búsqueda (ej: columna de Acciones).
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  if (typeof $ === 'undefined' || !$.fn.DataTable) return

  $('.js-datatable').each(function () {
    $(this).DataTable({
      language: {
        search: 'Buscar:',
        lengthMenu: 'Mostrar _MENU_',
        info: '_START_–_END_ de _TOTAL_',
        infoEmpty: 'Sin resultados',
        infoFiltered: '(filtrado de _MAX_ totales)',
        zeroRecords: 'Sin resultados',
        emptyTable: 'No hay datos disponibles',
        paginate: { first: '«', last: '»', next: '›', previous: '‹' },
      },
      pageLength: 10,
      // Sin orden inicial: respeta el orden que ya viene armado desde el servidor
      // (ej. admin de plataforma primero). El usuario puede reordenar clickeando una columna.
      order: [],
      columnDefs: [{ orderable: false, searchable: false, targets: 'nosort' }],
    })
  })
})
