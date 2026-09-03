import random
import string

from apps.companies.models import Branch

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


def sucursales_del_usuario(user):
    # Sucursales sobre las que el usuario puede operar:
    #   - manager/empleado -> solo la suya
    #   - admin            -> todas las activas de su empresa
    #   - superuser        -> todas las activas del sistema
    if user.branch_id:
        return Branch.objects.filter(id=user.branch_id)
    if user.is_superuser:
        return Branch.objects.filter(is_active=True)
    company = empresa_del_usuario(user)
    if company:
        return company.branches.filter(is_active=True)
    return Branch.objects.none()


def sucursales_de_empresa(user):
    # Todas las sucursales activas de la empresa del usuario (para elegir a cual
    # asignar stock al crear un producto, no solo la propia). Superuser -> todas.
    company = empresa_del_usuario(user)
    if company:
        return company.branches.filter(is_active=True)
    if user.is_superuser:
        return Branch.objects.filter(is_active=True)
    return Branch.objects.none()
