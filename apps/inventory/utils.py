import random
import string

from .models import ProductModel


def generar_sku(largo=12):
    # SKU aleatorio: mezcla de letras mayusculas y numeros, nunca menos de 10 caracteres.
    largo = max(largo, 10)
    letras = string.ascii_uppercase
    numeros = string.digits
    # Se fuerza al menos una letra y un numero; el resto es libre.
    chars = [random.choice(letras), random.choice(numeros)]
    chars += random.choices(letras + numeros, k=largo - 2)
    random.shuffle(chars)
    return "".join(chars)


def generar_sku_unico(company):
    # Reintenta hasta encontrar un SKU que no exista dentro de esa empresa.
    while True:
        sku = generar_sku()
        if not ProductModel.objects.filter(company=company, sku=sku).exists():
            return sku


def empresa_del_usuario(user):
    # Regla de negocio (CustomUser.clean): el admin se vincula por `company`;
    # el manager/empleado por `branch`, y su empresa es branch.company.
    if user.company_id:
        return user.company
    if user.branch_id:
        return user.branch.company
    return None
