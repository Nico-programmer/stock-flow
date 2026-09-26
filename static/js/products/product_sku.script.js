document.addEventListener('DOMContentLoaded', function () {
    const nameInput = document.getElementById('name')
    const skuInput = document.getElementById('sku')
    if (!nameInput || !skuInput) return

    const existingSkusData = document.getElementById('existing-skus-data')
    const existingSkus = existingSkusData ? JSON.parse(existingSkusData.textContent) : []

    // Si el SKU ya trae algo (edición, o un create re-renderizado tras un error), no se
    // pisa lo que el usuario ya puso/vio. Deja de autogenerarse en cuanto lo toca a mano.
    let skuManuallyEdited = skuInput.value.trim() !== ''

    // Solo letras del nombre, sin acentos ni espacios: no debe "leerse" el nombre completo,
    // apenas un prefijo corto (ver la consulta del usuario: no quiere que el SKU repita literal
    // lo que escribió, porque varios productos con nombres parecidos generarían el mismo texto).
    function prefixFromName(text) {
        const letters = text
            .normalize('NFD').replace(/[̀-ͯ]/g, '')
            .toUpperCase()
            .replace(/[^A-Z]/g, '')
        return (letters || 'PRD').slice(0, 3)
    }

    // Primer número libre para ese prefijo, mirando los SKU que ya existen en esta empresa
    // (existingSkus, inyectado por el server) para no proponer uno duplicado.
    function nextCode(prefix) {
        const pattern = new RegExp('^' + prefix + '-(\\d+)$')
        let max = 0
        existingSkus.forEach(function (sku) {
            const match = pattern.exec(sku)
            if (match) {
                const n = parseInt(match[1], 10)
                if (n > max) max = n
            }
        })
        return prefix + '-' + String(max + 1).padStart(3, '0')
    }

    nameInput.addEventListener('input', function () {
        if (skuManuallyEdited) return
        skuInput.value = nameInput.value.trim() ? nextCode(prefixFromName(nameInput.value)) : ''
    })

    skuInput.addEventListener('input', function () {
        skuManuallyEdited = true
    })
})
