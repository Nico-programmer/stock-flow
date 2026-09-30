document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('product-rows-container')
    const typeSelect = document.getElementById('movement_type')
    const totalEl = document.getElementById('movement-total')
    if (!container || !typeSelect || !totalEl) return

    function formatMoney(value) {
        return '$' + value.toLocaleString('es-CO', { maximumFractionDigits: 2 })
    }

    // Compra/devolución (Entrada) valen a precio de costo; venta/merma (Salida) a precio de
    // venta: es lo que el negocio paga o cobra en cada caso, no el mismo precio para las dos.
    function unitPriceFor(select) {
        const option = select.options[select.selectedIndex]
        if (!option || !option.value) return 0
        const field = typeSelect.value === 'IN' ? 'cost' : 'sale'
        return parseFloat(option.dataset[field] || '0') || 0
    }

    function recalculate() {
        let total = 0

        container.querySelectorAll('.product-row').forEach(function (row) {
            const select = row.querySelector('.js-product-select')
            const quantityInput = row.querySelector('.js-row-quantity')
            const subtotalEl = row.querySelector('.js-row-subtotal')
            if (!select || !quantityInput || !subtotalEl) return

            const quantity = parseFloat(quantityInput.value) || 0
            const subtotal = unitPriceFor(select) * quantity
            subtotalEl.textContent = formatMoney(subtotal)
            total += subtotal
        })

        totalEl.textContent = formatMoney(total)
    }

    // Delegado en el contenedor (no en cada fila): cubre también las filas que se agregan
    // después con "Agregar producto". Choices.js reemplaza el <select> por su propio widget
    // pero sigue disparando 'change' sobre el <select> original, así que esto alcanza.
    container.addEventListener('change', recalculate)
    container.addEventListener('input', recalculate)
    typeSelect.addEventListener('change', recalculate)

    recalculate()
})
