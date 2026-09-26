/* ============================================================
   datatables-init.js
   Inicializa DataTables (búsqueda, orden, paginación) en toda
   tabla marcada con class="js-datatable". Columnas con class="nosort"
   quedan fuera del orden/búsqueda (ej: columna de Acciones).

   Orden inicial: por default NINGUNO (respeta el orden que ya viene armado
   desde el servidor, ej. admin de plataforma primero en user_list). Una tabla
   puede pedir un orden ascendente por columna con data-order="<indice>",
   ej. <table class="js-datatable" data-order="0"> ordena asc por la 1ra columna.
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  if (typeof $ === 'undefined' || !$.fn.DataTable) return

  $('.js-datatable').each(function () {
    const orderCol = this.dataset.order
    const order = orderCol !== undefined ? [[parseInt(orderCol, 10), 'asc']] : []

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
      order: order,
      columnDefs: [{ orderable: false, searchable: false, targets: 'nosort' }],
    })
  })
})
