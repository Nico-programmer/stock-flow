document.getElementById('sidebarToggle')?.addEventListener('click', function () {
    document.querySelector('.sidebar').classList.toggle('show')
})

// DataTables: se aplica a cualquier <table class="js-datatable">.
// - Busqueda en vivo, orden y paginacion (client-side).
// - Cada <th data-filter> genera un <select> arriba de la tabla para filtrar esa columna.
// - Los <select> son EN CASCADA: al elegir un valor, los demas solo muestran las opciones
//   que siguen siendo posibles (ej. elegis Empresa -> Sucursal solo lista las de esa empresa).
// - El valor real de una celda (para buscar/filtrar) sale de data-search si existe, asi una
//   columna puede mostrar solo un icono y seguir siendo filtrable.
document.addEventListener('DOMContentLoaded', function () {
    if (!window.jQuery || !jQuery.fn.dataTable) return

    function escRegex(s) {
        return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    }

    jQuery('table.js-datatable').each(function () {
        const $t = jQuery(this)
        if ($t.hasClass('dataTable')) return   // evita doble init

        $t.DataTable({
            language: { url: 'https://cdn.datatables.net/plug-ins/2.1.8/i18n/es-ES.json' },
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            order: [],                                   // respeta el orden que manda el server
            columnDefs: [
                { targets: 'nosort', orderable: false }   // columnas .nosort (ej. Acciones)
            ],
            initComplete: function () {
                const api = this.api()

                // Columnas con <th data-filter>.
                const filterCols = []
                api.columns().every(function () {
                    const th = this.header()
                    if (th.getAttribute('data-filter') !== null) {
                        filterCols.push({ idx: this.index(), label: (th.textContent || '').trim() })
                    }
                })
                if (!filterCols.length) return

                // Matriz [fila][columna] con el valor de busqueda de cada celda (una sola vez).
                const rows = []
                api.rows().nodes().each(function (tr) {
                    const row = []
                    for (let i = 0; i < tr.children.length; i++) {
                        const td = tr.children[i]
                        row.push((td.getAttribute('data-search') || td.textContent || '').trim())
                    }
                    rows.push(row)
                })

                const active = {}    // idx -> valor elegido
                const selects = {}   // idx -> <select>

                function apply() {
                    filterCols.forEach(function (f) {
                        const v = active[f.idx] || ''
                        api.column(f.idx).search(v ? '^' + escRegex(v) + '$' : '', true, false)
                    })
                    api.draw()
                }

                // Opciones posibles para una columna, respetando TODOS los otros filtros activos.
                function optionsFor(idx) {
                    const vals = new Set()
                    rows.forEach(function (row) {
                        for (const k in active) {
                            if (+k === idx || !active[k]) continue
                            if (row[+k] !== active[k]) return
                        }
                        const v = row[idx]
                        if (v && v !== '—') vals.add(v)
                    })
                    return Array.from(vals).sort()
                }

                function rebuild() {
                    filterCols.forEach(function (f) {
                        const sel = selects[f.idx]
                        const cur = active[f.idx] || ''
                        const opts = optionsFor(f.idx)
                        if (cur && opts.indexOf(cur) === -1) opts.push(cur)   // no perder la seleccion

                        sel.innerHTML = '<option value="">' + f.label + ': todos</option>'
                        opts.forEach(function (v) {
                            const o = document.createElement('option')
                            o.value = v
                            o.textContent = v
                            if (v === cur) o.selected = true
                            sel.appendChild(o)
                        })
                    })
                }

                const bar = document.createElement('div')
                bar.className = 'd-flex flex-wrap align-items-center gap-2 mb-3 js-dt-filters'
                filterCols.forEach(function (f) {
                    const sel = document.createElement('select')
                    sel.className = 'form-select form-select-sm w-auto'
                    sel.addEventListener('change', function () {
                        active[f.idx] = this.value
                        apply()
                        rebuild()
                    })
                    selects[f.idx] = sel
                    bar.appendChild(sel)
                })
                rebuild()
                api.table().container().prepend(bar)
            }
        })
    })
})
