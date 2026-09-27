document.addEventListener('DOMContentLoaded', function () {
    if (typeof Choices === 'undefined') return

    // Cualquier <select class="js-select-search"> se vuelve buscable (Choices.js). Útil en
    // listas largas (ej. Categoría, Producto) donde scrollear un <select> normal es tedioso.
    document.querySelectorAll('.js-select-search').forEach(function (select) {
        new Choices(select, {
            searchEnabled: true,
            searchPlaceholderValue: 'Buscar...',
            noResultsText: 'Sin resultados',
            noChoicesText: 'No hay opciones',
            itemSelectText: '',
            shouldSort: false,
        })
    })
})
