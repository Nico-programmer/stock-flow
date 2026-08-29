document.querySelectorAll('.toggle-password').forEach(function (button) {
    button.addEventListener('click', function () {
        const targetId = button.getAttribute('data-target');
        const input = document.getElementById(targetId);
        const icon = button.querySelector('.fa-eye, .fa-eye-slash');

        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const companySelect = document.getElementById('company')
    const branchSelect = document.getElementById('branch')

    companySelect.addEventListener('change', function () {
        const companyId = this.value

        branchSelect.innerHTML = '<option value="" disabled selected>Cargando...</option>'
        branchSelect.disabled = true

        if (!companyId) return

        const url = branchesUrlTemplate.replace('0', companyId)

        fetch(url)
            .then(response => response.json())
            .then(branches => {
                branchSelect.innerHTML = '<option value="" disabled selected>Selecciona la sucursal</option>'

                if (branches.length === 0) {
                    branchSelect.innerHTML = '<option value="" disabled selected>Sin sucursales activas</option>'
                    return
                }

                branches.forEach(branch => {
                    const option = document.createElement('option')
                    option.value = branch.id
                    option.textContent = branch.name
                    branchSelect.appendChild(option)
                })

                branchSelect.disabled = false
            })
            .catch(() => {
                branchSelect.innerHTML = '<option value="" disabled selected>Error al cargar sucursales</option>'
            })
    })
})