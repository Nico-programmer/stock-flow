document.addEventListener('DOMContentLoaded', function () {
    const typeSelect = document.getElementById('movement_type')
    const reasonSelect = document.getElementById('reason')
    if (!typeSelect || !reasonSelect) return

    // Cada <option> de Motivo trae data-type (ej. "IN", "OUT" o "IN OUT" para ajuste, ver
    // Movement.REASONS_BY_TYPE en el modelo): acá se ocultan las que no apliquen al tipo elegido.
    function applyFilter() {
        const type = typeSelect.value
        let selectedStillValid = false

        Array.from(reasonSelect.options).forEach(function (option) {
            if (!option.value) return // el placeholder siempre queda visible

            const types = (option.dataset.type || '').split(' ')
            const visible = !type || types.includes(type)
            option.hidden = !visible
            option.disabled = !visible
            if (visible && option.selected) selectedStillValid = true
        })

        if (!selectedStillValid) {
            reasonSelect.value = ''
        }
    }

    typeSelect.addEventListener('change', applyFilter)
    applyFilter()
})
