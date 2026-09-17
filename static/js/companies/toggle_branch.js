document.addEventListener('DOMContentLoaded', function () {
    // The CSRF token is obtained from any form already present on the page.
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value
    }

    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.toggle-branch')
        if (!btn) return

        const url = btn.dataset.url
        const confirmMsg = btn.dataset.confirm

        if (!confirm(confirmMsg)) return

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
        })
            .then(function (response) {
                if (response.ok || response.redirect) {
                    window.location.reload() // It reloads to reflect the new state
                } else {
                    alert('Ocurrió un error al actualizar la sucursal.')
                }
            })
            .catch(function () {
                alert('Ocurrió un error de conexión.')
            })
    })
})