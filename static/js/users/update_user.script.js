document.addEventListener('DOMContentLoaded', function () {
    const companySelect = document.getElementById('company')
    const groupSelect = document.getElementById('group')

    const currentGroupId = groupSelect.dataset.current || ''

    function loadGroups(companyId, selectedGroupId) {
        groupSelect.innerHTML = '<option value="" selected>Cargando...</option>'
        groupSelect.disabled = true

        if (!companyId) return

        const url = groupsUrlTemplate.replace('0', companyId)

        fetch(url)
            .then(response => response.json())
            .then(groups => {
                groupSelect.innerHTML = '<option value="">Sin grupo</option>'

                groups.forEach(group => {
                    const option = document.createElement('option')
                    option.value = group.id
                    option.textContent = group.name
                    if (String(group.id) === String(selectedGroupId)) {
                        option.selected = true
                    }
                    groupSelect.appendChild(option)
                })

                groupSelect.disabled = false
            })
            .catch(() => {
                groupSelect.innerHTML = '<option value="">Error al cargar grupos</option>'
            })
    }

    if (companySelect.value) {
        loadGroups(companySelect.value, currentGroupId)
    }

    companySelect.addEventListener('change', function () {
        loadGroups(this.value, '')
    })
})
