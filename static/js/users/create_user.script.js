document.addEventListener('DOMContentLoaded', function () {
    const companySelect = document.getElementById('company')
    const groupSelect = document.getElementById('group')
    const branchSelect = document.getElementById('branch')

    const currentGroupId = groupSelect.dataset.current || ''
    const currentBranchId = branchSelect.dataset.current || ''

    function loadGroups(companyId, selectedGroupId) {
        groupSelect.innerHTML = '<option value="" selected>Cargando...</option>'
        groupSelect.disabled = true

        if (!companyId) return

        const url = groupsUrlTemplate.replace('0', companyId)

        fetch(url)
            .then(response => response.json())
            .then(groups => {
                groupSelect.innerHTML = '<option value="">Sin grupo</option>'

                // Solo el admin de plataforma da de alta al usuario "dueño" de la empresa, por eso
                // el fallback a full-access aplica únicamente ahí. Un usuario de negocio dando de
                // alta a un empleado no debería arrancar en el grupo de mayor acceso por default.
                const fallbackGroupId = (!selectedGroupId && isAdminCreator)
                    ? (groups.find(group => group.full_access) || {}).id
                    : null

                groups.forEach(group => {
                    const option = document.createElement('option')
                    option.value = group.id
                    option.textContent = group.name
                    if (String(group.id) === String(selectedGroupId) || String(group.id) === String(fallbackGroupId)) {
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

    function loadBranches(companyId, selectedBranchId) {
        branchSelect.innerHTML = '<option value="" selected>Cargando...</option>'
        branchSelect.disabled = true

        if (!companyId) return

        const url = branchesUrlTemplate.replace('0', companyId)

        fetch(url)
            .then(response => response.json())
            .then(branches => {
                branchSelect.innerHTML = '<option value="">Sin sucursal (ve todas)</option>'

                branches.forEach(branch => {
                    const option = document.createElement('option')
                    option.value = branch.id
                    option.textContent = branch.name
                    if (String(branch.id) === String(selectedBranchId)) {
                        option.selected = true
                    }
                    branchSelect.appendChild(option)
                })

                branchSelect.disabled = false
            })
            .catch(() => {
                branchSelect.innerHTML = '<option value="">Error al cargar sucursales</option>'
            })
    }

    if (companySelect.value) {
        loadGroups(companySelect.value, currentGroupId)
        loadBranches(companySelect.value, currentBranchId)
    }

    companySelect.addEventListener('change', function () {
        loadGroups(this.value, '')
        loadBranches(this.value, '')
    })
})
