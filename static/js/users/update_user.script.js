document.addEventListener('DOMContentLoaded', function () {
    const companySelect = document.getElementById('company')
    const branchSelect = document.getElementById('branch')
    const roleSelect = document.getElementById('role')
    const branchWrapper = branchSelect.closest('.col-md-6')
    const permissionsCard = document.getElementById('permissions-card')

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

    function toggleFieldsByRole() {
        const isAdmin = roleSelect.value === 'admin'
        branchWrapper.style.display = isAdmin ? 'none' : ''
        if (permissionsCard) permissionsCard.style.display = isAdmin ? 'none' : ''

        document.querySelectorAll('#permissions-card input[type="checkbox"]').forEach(function (checkbox) {
            if (isAdmin) {
                checkbox.dataset.previousState = checkbox.checked  // se guarda el estado antes de forzarlo
                checkbox.checked = true
                checkbox.disabled = true
            } else {
                checkbox.disabled = false
                if (checkbox.dataset.previousState !== undefined) {
                    checkbox.checked = checkbox.dataset.previousState === 'true'
                }
            }
        })
    }

    if (companySelect.value) {
        loadBranches(companySelect.value, currentBranchId)
    }

    companySelect.addEventListener('change', function () {
        loadBranches(this.value, '')
    })

    roleSelect.addEventListener('change', toggleFieldsByRole)
    toggleFieldsByRole()
})