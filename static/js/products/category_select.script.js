document.addEventListener('DOMContentLoaded', function () {
    const categorySelect = document.getElementById('category')
    if (!categorySelect || typeof Choices === 'undefined') return

    new Choices(categorySelect, {
        searchEnabled: true,
        searchPlaceholderValue: 'Buscar categoría...',
        noResultsText: 'Sin resultados',
        noChoicesText: 'No hay categorías',
        itemSelectText: '',
        shouldSort: false,
    })
})
