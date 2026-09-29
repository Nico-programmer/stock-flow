/* ============================================================
   datatables-init.js
   Inicializa DataTables (búsqueda, orden, paginación) en toda
   tabla marcada con class="js-datatable". Columnas con class="nosort"
   quedan fuera del orden/búsqueda (ej: columna de Acciones).

   Orden inicial: por default NINGUNO (respeta el orden que ya viene armado
   desde el servidor, ej. admin de plataforma primero en user_list). Una tabla
   puede pedir un orden por columna con data-initial-order="<indice>" (asc por
   default) o data-initial-order="<indice>,desc", ej.
   <table class="js-datatable" data-initial-order="6,desc"> ordena desc por la
   7ma columna (columnas 0-indexadas).
   NOTA: no usar "data-order" para esto — DataTables lo reserva como atributo
   de auto-init en el <table> (espera JSON, ej. data-order='[[1,"asc"]]') y si
   no matchea ese formato rompe la inicialización completa de la tabla.
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
  if (typeof $ === 'undefined' || !$.fn.DataTable) return

  $('.js-datatable').each(function () {
    const orderCol = this.dataset.initialOrder
    let order = []
    if (orderCol !== undefined) {
      const [colIndex, direction] = orderCol.split(',')
      order = [[parseInt(colIndex, 10), direction === 'desc' ? 'desc' : 'asc']]
    }

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
