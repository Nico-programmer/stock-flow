document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form.classList || !form.classList.contains('js-confirm-submit')) return;
    if (form.dataset.confirmed === 'true') return;

    event.preventDefault();

    Swal.fire({
        icon: form.dataset.confirmIcon || 'warning',
        title: form.dataset.confirmTitle || '¿Estás seguro?',
        text: form.dataset.confirmText || '',
        showCancelButton: true,
        confirmButtonText: form.dataset.confirmButton || 'Sí, continuar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#1657D6',
    }).then(function (result) {
        if (result.isConfirmed) {
            form.dataset.confirmed = 'true';
            form.submit();
        }
    });
});
