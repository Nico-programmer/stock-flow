from decimal import Decimal, InvalidOperation

from django.shortcuts import render,redirect, get_object_or_404

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.core.exceptions import ValidationError

from django.urls import reverse

from django.db import transaction, IntegrityError

from apps.companies.models import Company, Branch

from .models import *
from .utils import empresa_del_usuario, generar_sku_unico, sucursales_del_usuario, sucursales_de_empresa

"""------------------------------------------------------------------ Inventory Views ------------------------------------------------------------------"""

# Inventario
@login_required
def inventory_list(request):
    return render(request, "inventory/inventory_list.html")

"""------------------------------------------------------------------ Products Views ------------------------------------------------------------------"""

# Umbral de "stock bajo": a partir de acá el producto se marca en amarillo.
LOW_STOCK = 5

# Products
@login_required
def product_list(request):
    # Busqueda / orden / paginacion / filtros de columna: todo lo hace DataTables en el cliente.
    # El server solo decide QUE filas se cargan segun el alcance del usuario.
    company = empresa_del_usuario(request.user)
    is_super = request.user.is_superuser

    if is_super:
        # Superuser: TODAS las filas de TODAS las empresas.
        branches = Branch.objects.none()
        stocks = (BranchStock.objects
                  .select_related('product', 'branch', 'branch__company')
                  .order_by('branch__company__name', 'branch__name', 'product__name'))
    else:
        # Resto: solo las sucursales a las que tiene acceso (1 para manager/empleado, varias para admin).
        branches = sucursales_del_usuario(request.user).select_related('company')
        stocks = (BranchStock.objects
                  .select_related('product', 'branch')
                  .filter(branch__in=branches)
                  .order_by('branch__name', 'product__name'))

    # Columna de sucursal: siempre para superuser; para el resto solo si maneja mas de una.
    show_branch_col = is_super or branches.count() > 1

    context = {
        'products': stocks,   # cada item es un BranchStock (usar p.product.* y p.stock)
        'company': company,
        'is_super': is_super,
        'show_branch_col': show_branch_col,
        'low_stock': LOW_STOCK,
    }
    return render(request, "products/product_list.html", context)

@login_required
def create_product(request):
    # La empresa sale del usuario. Excepcion: superuser sin empresa -> la elige.
    company = empresa_del_usuario(request.user)
    puede_elegir_empresa = company is None and request.user.is_superuser
    companies = Company.objects.filter(is_active=True) if puede_elegir_empresa else None

    def resolver_empresa(cid):
        # Empresa efectiva: la del usuario, o la elegida por el superuser (validada).
        if company is not None:
            return company
        if puede_elegir_empresa and cid:
            return Company.objects.filter(id=cid, is_active=True).first()
        return None

    if request.method == 'POST':
        # Campos crudos del POST. El SKU no se pide: se autogenera mas abajo.
        name = request.POST.get("name", "").strip()
        brand = request.POST.get("brand", "").strip()
        price_raw = request.POST.get("price", "").strip()
        company_id = request.POST.get("company", "").strip()

        eff_company = resolver_empresa(company_id)
        branches = eff_company.branches.filter(is_active=True) if eff_company else Branch.objects.none()

        # filas: (sucursal, valor de stock tal cual lo mando el usuario) para repoblar el form.
        filas = [(b, request.POST.get(f"stock_{b.id}", "").strip()) for b in branches]

        base_context = {
            'company_name': eff_company.name if eff_company else "",
            'companies': companies,
            'selected_company': company_id,
            'filas': filas,
            'name': name,
            'brand': brand,
            'price': price_raw,
        }

        # Se acumulan TODOS los checks primero; recien despues se toca la base de datos.
        errors = []

        if eff_company is None:
            errors.append("Debes seleccionar una empresa valida.")
        elif not branches:
            errors.append("La empresa no tiene sucursales activas.")
        if not name:
            errors.append("El nombre es obligatorio.")
        if not brand:
            errors.append("La marca es obligatoria.")

        # Precio: debe ser un decimal >= 0. Los datos del POST son strings, hay que convertir.
        price = None
        if not price_raw:
            errors.append("El precio es obligatorio.")
        else:
            try:
                price = Decimal(price_raw)
                if price < 0:
                    errors.append("El precio debe ser mayor o igual a 0.")
            except InvalidOperation:
                errors.append("El precio no es un numero valido.")

        # Stock por sucursal: entero >= 0. Vacio = 0.
        nuevos_stocks = {}
        for b, raw in filas:
            raw = raw or "0"
            try:
                valor = int(raw)
                if valor < 0:
                    errors.append(f"El stock de {b.name} debe ser mayor o igual a 0.")
                else:
                    nuevos_stocks[b.id] = valor
            except ValueError:
                errors.append(f"El stock de {b.name} no es un numero valido.")

        if errors:
            messages.error(request, errors[0])   # se muestra solo el primer error
            return render(request, "products/create_product.html", base_context)

        # SKU autogenerado: 12 caracteres (siempre >= 10), letras + numeros, unico por empresa.
        sku = generar_sku_unico(eff_company)

        try:
            # atomic(): se crean producto + stock de todas las sucursales juntos, o nada.
            with transaction.atomic():
                product = ProductModel(
                    company=eff_company,
                    sku=sku,
                    name=name,
                    brand=brand,
                    price=price,
                )
                product.full_clean()   # valida MinValueValidator, unique_sku_per_company, etc.
                product.save()

                for b in branches:
                    bs = BranchStock(product=product, branch=b, stock=nuevos_stocks[b.id])
                    bs.full_clean()   # valida "misma empresa" y unique_product_per_branch
                    bs.save()
        except (IntegrityError, ValidationError):
            # IntegrityError: choque de unique en BD. ValidationError: falla de full_clean().
            messages.error(request, "Ocurrio un error al crear el producto. Intenta de nuevo.")
            return render(request, "products/create_product.html", base_context)

        # Exito: SweetAlert + redirect al listado (mismo patron que create_user).
        messages.success(request, f"Producto {product.name} creado correctamente.")
        return render(request, "products/create_product.html", {
            'redirect_url': reverse('inventory:product_list'),
        })

    # GET: si el superuser ya eligio empresa (?company=<id>), se muestran sus sucursales.
    company_id = request.GET.get("company", "").strip()
    eff_company = resolver_empresa(company_id)
    branches = eff_company.branches.filter(is_active=True) if eff_company else Branch.objects.none()
    filas = [(b, "") for b in branches]
    return render(request, "products/create_product.html", {
        'company_name': eff_company.name if eff_company else "",
        'companies': companies,
        'selected_company': company_id,
        'filas': filas,
    })

@login_required
def update_product(request, product_id):
    product = get_object_or_404(ProductModel, id=product_id)

    # Solo se puede editar un producto de la propia empresa (el superuser puede todo).
    if not request.user.is_superuser and product.company_id != getattr(empresa_del_usuario(request.user), 'id', None):
        messages.error(request, "No puedes editar este producto.")
        return redirect("inventory:product_list")

    # TODAS las sucursales de la empresa; para cada una su fila de stock (o None si aun no existe).
    branches = sucursales_de_empresa(request.user)
    existentes = {bs.branch_id: bs for bs in BranchStock.objects.filter(product=product)}
    filas = [(b, existentes.get(b.id)) for b in branches]

    if request.method == 'POST':
        # Datos de catalogo (nivel empresa).
        name = request.POST.get("name", "").strip()
        brand = request.POST.get("brand", "").strip()
        price_raw = request.POST.get("price", "").strip()

        errors = []
        if not name:
            errors.append("El nombre es obligatorio.")
        if not brand:
            errors.append("La marca es obligatoria.")

        price = None
        if not price_raw:
            errors.append("El precio es obligatorio.")
        else:
            try:
                price = Decimal(price_raw)
                if price < 0:
                    errors.append("El precio debe ser mayor o igual a 0.")
            except InvalidOperation:
                errors.append("El precio no es un numero valido.")

        # Stock por sucursal: un input name="stock_<branch_id>" por cada sucursal.
        nuevos_stocks = {}
        for b, _bs in filas:
            raw = request.POST.get(f"stock_{b.id}", "").strip()
            try:
                valor = int(raw)
                if valor < 0:
                    errors.append(f"El stock de {b.name} debe ser mayor o igual a 0.")
                else:
                    nuevos_stocks[b.id] = valor
            except ValueError:
                errors.append(f"El stock de {b.name} no es un numero valido.")

        if errors:
            messages.error(request, errors[0])
            return render(request, "products/update_product.html", {
                'product': product, 'filas': filas,
            })

        try:
            with transaction.atomic():
                product.name = name
                product.brand = brand
                product.price = price
                product.full_clean()
                product.save()

                for b, _bs in filas:
                    BranchStock.objects.update_or_create(
                        product=product, branch=b,
                        defaults={'stock': nuevos_stocks[b.id]},
                    )
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrio un error al actualizar el producto. Intenta de nuevo.")
            return render(request, "products/update_product.html", {
                'product': product, 'filas': filas,
            })

        messages.success(request, f"Producto {product.name} actualizado correctamente.")
        existentes = {bs.branch_id: bs for bs in BranchStock.objects.filter(product=product)}
        filas = [(b, existentes.get(b.id)) for b in branches]
        return render(request, "products/update_product.html", {
            'product': product, 'filas': filas,
            'redirect_url': reverse('inventory:product_list'),
        })

    return render(request, "products/update_product.html", {
        'product': product, 'filas': filas,
    })

@login_required
def active_product(request, product_id):
    product = get_object_or_404(ProductModel, id=product_id)
    product.is_active = True
    product.save()

    return redirect("inventory:product_list")

@login_required
def inactive_product(request, product_id):
    product = get_object_or_404(ProductModel, id=product_id)
    product.is_active = False
    product.save()

    return redirect("inventory:product_list")