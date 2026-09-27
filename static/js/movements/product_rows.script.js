document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('product-rows-container')
    const template = document.getElementById('product-row-template')
    const addBtn = document.getElementById('add-product-row')
    if (!container || !template || !addBtn) return

    // Cada fila necesita su propio Choices.js (buscador): se inicializa acá en vez de con el
    // script genérico, porque las filas agregadas después del DOMContentLoaded también lo necesitan.
    function initSelectSearch(select) {
        if (typeof Choices === 'undefined' || select.dataset.choicesInit) return
        new Choices(select, {
            searchEnabled: true,
            searchPlaceholderValue: 'Buscar producto...',
            noResultsText: 'Sin resultados',
            noChoicesText: 'No hay productos',
            itemSelectText: '',
            shouldSort: false,
        })
        select.dataset.choicesInit = 'true'
    }

    container.querySelectorAll('.js-product-select').forEach(initSelectSearch)

    addBtn.addEventListener('click', function () {
        const clone = template.content.cloneNode(true)
        container.appendChild(clone)
        const newSelect = container.querySelector('.product-row:last-child .js-product-select')
        if (newSelect) initSelectSearch(newSelect)
    })

    container.addEventListener('click', function (e) {
        const removeBtn = e.target.closest('.remove-product-row')
        if (!removeBtn) return

        const rows = container.querySelectorAll('.product-row')
        if (rows.length > 1) {
            removeBtn.closest('.product-row').remove()
        }
    })
})
