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

                // Si no venía un grupo ya elegido (alta nueva), se preselecciona el de mayor acceso:
                // quien da de alta al usuario es el admin de plataforma, así que por defecto es
                // el "dueño" de la empresa, no un empleado sin permisos.
                const fallbackGroupId = !selectedGroupId
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

    if (companySelect.value) {
        loadGroups(companySelect.value, currentGroupId)
    }

    companySelect.addEventListener('change', function () {
        loadGroups(this.value, '')
    })
})
