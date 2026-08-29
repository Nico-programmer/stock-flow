document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('branches-container')
    const template = document.getElementById('branch-row-template')
    const addBtn = document.getElementById('add-branch')

    addBtn.addEventListener('click', function () {
        const clone = template.content.cloneNode(true)
        container.appendChild(clone)
    })

    container.addEventListener('click', function (e) {
        const removeBtn = e.target.closest('.remove-branch')
        if (!removeBtn) return

        const rows = container.querySelectorAll('.branch-row')
        if (rows.length > 1) {
            removeBtn.closest('.branch-row').remove()
        }
    })
})