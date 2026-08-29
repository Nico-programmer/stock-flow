document.addEventListener('DOMContentLoaded', function () {
    const companySelect = document.getElementById('company')
    const branchSelect = document.getElementById('branch')

    // El id de la sucursal actual, si existe, para dejarla preseleccionada tras cargar
    const currentBranchId = branchSelect.dataset.current || ''

    function loadBranches(companyId, selectedBranchId) {
        branchSelect.innerHTML = '<option value="" disabled selected>Cargando...</option>'
        branchSelect.disabled = true

        if (!companyId) return

        const url = branchesUrlTemplate.replace('0', companyId)

        fetch(url)
            .then(response => response.json())
            .then(branches => {
                branchSelect.innerHTML = '<option value="" disabled>Selecciona la sucursal</option>'

                if (branches.length === 0) {
                    branchSelect.innerHTML = '<option value="" disabled selected>Sin sucursales activas</option>'
                    return
                }

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
                branchSelect.innerHTML = '<option value="" disabled selected>Error al cargar sucursales</option>'
            })
    }

    // Si al cargar la página ya hay una empresa seleccionada (modo edición), carga sus sucursales de una vez
    if (companySelect.value) {
        loadBranches(companySelect.value, currentBranchId)
    }

    // Si el usuario cambia de empresa manualmente, se recargan las sucursales (sin preseleccionar ninguna)
    companySelect.addEventListener('change', function () {
        loadBranches(this.value, '')
    })
})