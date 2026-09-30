document.addEventListener('DOMContentLoaded', function () {
    if (typeof $ === 'undefined' || !$.fn.DataTable) return
    const el = document.getElementById('movements-table')
    if (!el) return

    // Una celda con data-order (ver la de Fecha) hace que DataTables devuelva un objeto
    // { display, ... } en vez de un string plano; con esto se cubren los dos casos.
    function cellHtml(value) {
        if (value && typeof value === 'object') return value.display || ''
        return value || ''
    }

    function stripHtml(html) {
        const tmp = document.createElement('div')
        tmp.innerHTML = cellHtml(html)
        return (tmp.textContent || tmp.innerText || '').trim()
    }

    function parseMoney(html) {
        return parseFloat(stripHtml(html).replace(/[^0-9.-]/g, '')) || 0
    }

    const orderCol = el.dataset.initialOrder ? parseInt(el.dataset.initialOrder.split(',')[0], 10) : 7

    const table = $(el).DataTable({
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
        order: [[orderCol, 'asc']],
        columnDefs: [
            { targets: [1, 2, 4, 6, 7, 8], visible: false },
            { targets: 8, searchable: false, orderable: false },
        ],
        rowGroup: {
            dataSrc: 8,
            startRender: function (rows, group) {
                const first = rows.data()[0]
                const sucursal = stripHtml(first[1])
                const tipo = first[2] // ya viene como badge (HTML), se reusa tal cual
                const motivo = stripHtml(first[4])
                const usuario = stripHtml(first[6])
                const fecha = stripHtml(first[7])

                let total = 0
                rows.data().each(function (row) { total += parseMoney(row[5]) })

                const visibleCols = $(el).find('thead th:visible').length

                return $('<tr/>').addClass('rowgroup-header').append(
                    '<td colspan="' + visibleCols + '">' +
                        '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2">' +
                            '<div class="d-flex flex-wrap align-items-center gap-2">' +
                                tipo +
                                '<strong>' + sucursal + '</strong>' +
                                '<span class="text-muted-soft">' + motivo + '</span>' +
                                '<span class="text-muted-soft">' + usuario + '</span>' +
                                '<span class="text-muted-soft">' + fecha + '</span>' +
                            '</div>' +
                            '<strong>Total: $' + total.toLocaleString('es-CO') + '</strong>' +
                        '</div>' +
                    '</td>'
                )
            },
        },
    })
})
