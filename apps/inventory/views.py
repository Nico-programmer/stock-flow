from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum, Exists, OuterRef, F
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from apps.accounts.decorators import platform_admin_required, inventory_access_required
from apps.companies.models import Company
from .models import Category, Product, Stock

"""------------------------------------------------------------------ Category Views ------------------------------------------------------------------"""

@login_required
@platform_admin_required
def category_list(request):
    categories = Category.objects.order_by('name')
    return render(request, "categories/category_list.html", {'categories': categories})

@login_required
@platform_admin_required
def create_category(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        base_context = {'name': name}

        errors = []

        if not name:
            errors.append("El nombre de la categoría es obligatorio.")
        if name and len(name) > 100:
            errors.append("El nombre de la categoría no puede superar los 100 caracteres.")
        if name and Category.objects.filter(name=name).exists():
            errors.append("Ya existe una categoría con ese nombre.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'categories/create_category.html', base_context)

        Category.objects.create(name=name)

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"Categoría {name} creada correctamente.")
        return render(request, 'categories/create_category.html', {
            'redirect_url': reverse('inventory:category_list'),
        })

    # GET: form vacío.
    return render(request, 'categories/create_category.html')

@login_required
@platform_admin_required
def update_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    context = {'category': category}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        # Se re-renderiza el form conservando lo que el admin ya había escrito, si hay que volver a mostrarlo.
        submitted_context = {**context, 'name': name}

        errors = []

        if not name:
            errors.append("El nombre de la categoría es obligatorio.")
        if name and len(name) > 100:
            errors.append("El nombre de la categoría no puede superar los 100 caracteres.")
        # exclude(id=category.id): que la propia categoría no cuente como "duplicada" de sí misma.
        if name and Category.objects.filter(name=name).exclude(id=category.id).exists():
            errors.append("Ya existe una categoría con ese nombre.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'categories/update_category.html', submitted_context)

        try:
            category.name = name
            category.full_clean()
            category.save()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar la categoría. Inténtalo de nuevo.")
            return render(request, "categories/update_category.html", submitted_context)

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"La categoría {name} fue editada exitosamente.")
        context['redirect_url'] = reverse('inventory:category_list')

    return render(request, 'categories/update_category.html', context)

# Elimina una categoría. SET_NULL: los productos que la tenían quedan sin categoría (Product.category on_delete=SET_NULL).
@login_required
@require_POST
@platform_admin_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    return redirect('inventory:category_list')

"""------------------------------------------------------------------ Product Views ------------------------------------------------------------------"""

# Resuelve sobre qué empresa se trabaja: la propia del usuario, o -si es admin de plataforma
# dando soporte- la que eligió por company_id. None si no hay una empresa válida para ver.
def _resolve_company(request, company_id):
    if company_id is not None:
        if not request.user.is_platform_admin:
            return None
        return get_object_or_404(Company, id=company_id)
    if request.user.is_platform_admin:
        return None
    return request.user.company

def _product_list_url(request, company):
    if request.user.is_platform_admin:
        return reverse('inventory:product_list', args=[company.id])
    return reverse('inventory:product_list')

@login_required
@inventory_access_required
def product_list(request, company_id=None):
    company = _resolve_company(request, company_id)
    if company is None:
        if request.user.is_platform_admin:
            messages.error(request, "Selecciona una empresa desde el listado.")
            return redirect('company:list')
        messages.error(request, "No tienes permiso para ver esta empresa.")
        return redirect('dashboard')

    # "Bajo" es por sucursal, no por el total sumado: una sucursal en 0 con otra sobrada
    # da un total que parece sano, pero esa sucursal puntual sí necesita reabastecerse.
    low_stock_subquery = Stock.objects.filter(product=OuterRef('pk'), quantity__lte=F('product__min_stock'))
    products = (
        Product.objects.filter(company=company)
        .select_related('category')
        .annotate(
            total_stock=Coalesce(Sum('stocks__quantity'), 0),
            has_low_stock=Exists(low_stock_subquery),
        )
        .order_by('name')
    )
    return render(request, "products/product_list.html", {'company': company, 'products': products})

@login_required
@inventory_access_required
def product_detail(request, product_id):
    product = get_object_or_404(Product.objects.select_related('company', 'category'), id=product_id)

    if not request.user.is_platform_admin and product.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para ver este producto.")
        return redirect('dashboard')

    stocks = Stock.objects.filter(product=product).select_related('branch').order_by('branch__name')
    total_stock = sum(s.quantity for s in stocks)
    return render(request, "products/product_detail.html", {
        'product': product, 'stocks': stocks, 'total_stock': total_stock,
    })

@login_required
@inventory_access_required
def create_product(request, company_id=None):
    company = _resolve_company(request, company_id)
    if company is None:
        if request.user.is_platform_admin:
            messages.error(request, "Selecciona una empresa desde el listado.")
            return redirect('company:list')
        messages.error(request, "No tienes permiso para ver esta empresa.")
        return redirect('dashboard')

    categories_qs = Category.objects.order_by('name')
    # El front usa esto para armar un SKU que no choque con uno ya usado por esta empresa
    # (ver static/js/products/product_sku.script.js), sin tener que ir preguntándole al server.
    existing_skus = list(Product.objects.filter(company=company).values_list('sku', flat=True))
    # Se pide la existencia inicial por sucursal en el mismo form: el usuario pidió no tener
    # que crear el producto y después ir a otra pantalla aparte a cargarle el stock.
    branches_qs = company.branches.filter(is_active=True).order_by('name')
    branch_names = {b.id: b.name for b in branches_qs}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        sku = request.POST.get("sku", "").strip()
        unit = request.POST.get("unit", "").strip()
        category_id = request.POST.get("category", "").strip()
        cost_price_raw = request.POST.get("cost_price", "").strip()
        sale_price_raw = request.POST.get("sale_price", "").strip()
        min_stock_raw = request.POST.get("min_stock", "").strip()
        # Una cantidad por sucursal, en paralelo a branches_qs (input name="stock_<branch.id>").
        stock_raw_by_branch = {b.id: request.POST.get(f"stock_{b.id}", "").strip() for b in branches_qs}

        base_context = {
            'company': company,
            'categories': categories_qs,
            'existing_skus': existing_skus,
            'branches': branches_qs,
            'name': name, 'sku': sku, 'unit': unit, 'selected_category': category_id,
            'cost_price': cost_price_raw, 'sale_price': sale_price_raw, 'min_stock': min_stock_raw,
            'stock_by_branch': stock_raw_by_branch,
        }

        errors = []

        if not name:
            errors.append("El nombre del producto es obligatorio.")
        if not sku:
            errors.append("El código (SKU) es obligatorio.")
        if sku and Product.objects.filter(company=company, sku=sku).exists():
            errors.append("Ya existe un producto con ese código en esta empresa.")
        if not category_id:
            errors.append("Selecciona una categoría.")
        if not unit:
            errors.append("La unidad es obligatoria.")

        cost_price = sale_price = None
        if not cost_price_raw:
            errors.append("El precio de costo es obligatorio.")
        else:
            try:
                cost_price = Decimal(cost_price_raw)
                if cost_price <= 0:
                    errors.append("El precio de costo debe ser mayor a cero.")
            except InvalidOperation:
                errors.append("El precio de costo no es válido.")

        if not sale_price_raw:
            errors.append("El precio de venta es obligatorio.")
        else:
            try:
                sale_price = Decimal(sale_price_raw)
                if sale_price <= 0:
                    errors.append("El precio de venta debe ser mayor a cero.")
            except InvalidOperation:
                errors.append("El precio de venta no es válido.")

        if cost_price is not None and sale_price is not None and sale_price <= cost_price:
            errors.append("El precio de venta debe ser mayor al precio de costo.")

        min_stock = None
        if not min_stock_raw:
            errors.append("El stock mínimo es obligatorio.")
        elif not min_stock_raw.isdigit():
            errors.append("El stock mínimo debe ser un número entero.")
        elif int(min_stock_raw) < 5:
            errors.append("El stock mínimo no puede ser menor a 5.")
        else:
            min_stock = int(min_stock_raw)

        # Vacío = 0 (sucursal arranca sin existencia); si trae algo, tiene que ser un entero >= 0.
        stock_by_branch = {}
        for branch_id, raw in stock_raw_by_branch.items():
            if not raw:
                stock_by_branch[branch_id] = 0
            elif raw.isdigit():
                stock_by_branch[branch_id] = int(raw)
            else:
                errors.append("La cantidad inicial de cada sucursal debe ser un número entero.")
                break

        if errors:
            messages.error(request, errors[0])
            return render(request, 'products/create_product.html', base_context)

        category_obj = get_object_or_404(Category, id=category_id)

        try:
            with transaction.atomic():
                product = Product(
                    company=company, category=category_obj,
                    name=name, sku=sku, unit=unit,
                    cost_price=cost_price, sale_price=sale_price, min_stock=min_stock,
                )
                product.full_clean()
                product.save()

                Stock.objects.bulk_create([
                    Stock(product=product, branch_id=branch_id, quantity=quantity)
                    for branch_id, quantity in stock_by_branch.items()
                ])
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al crear el producto. Inténtalo de nuevo.")
            return render(request, 'products/create_product.html', base_context)

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"Producto {name} creado correctamente.")

        # Aviso aparte (no bloquea el guardado) si alguna sucursal quedó en o por debajo del mínimo.
        low_branches = [branch_names[bid] for bid, qty in stock_by_branch.items() if qty <= min_stock]
        if low_branches:
            messages.warning(request, f"Quedó con stock bajo en: {', '.join(low_branches)}.")

        return render(request, 'products/create_product.html', {
            'company': company,
            'categories': categories_qs,
            'existing_skus': existing_skus + [sku],
            'branches': branches_qs,
            'redirect_url': _product_list_url(request, company),
        })

    # GET: form vacío.
    return render(request, 'products/create_product.html', {
        'company': company, 'categories': categories_qs, 'existing_skus': existing_skus, 'branches': branches_qs,
    })

@login_required
@inventory_access_required
def update_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if not request.user.is_platform_admin and product.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este producto.")
        return redirect('dashboard')

    categories_qs = Category.objects.order_by('name')
    # Todas las sucursales activas, no solo las que ya tienen Stock: cubre productos creados
    # antes de que la sucursal existiera, o sin stock inicial, y sucursales nuevas que se abran después.
    branches_qs = product.company.branches.filter(is_active=True).order_by('name')
    branch_names = {b.id: b.name for b in branches_qs}
    current_stock_by_branch = dict(Stock.objects.filter(product=product).values_list('branch_id', 'quantity'))
    context = {
        'product': product, 'categories': categories_qs, 'branches': branches_qs,
        'stock_by_branch': {b.id: current_stock_by_branch.get(b.id, 0) for b in branches_qs},
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        sku = request.POST.get("sku", "").strip()
        unit = request.POST.get("unit", "").strip()
        category_id = request.POST.get("category", "").strip()
        cost_price_raw = request.POST.get("cost_price", "").strip()
        sale_price_raw = request.POST.get("sale_price", "").strip()
        min_stock_raw = request.POST.get("min_stock", "").strip()
        stock_raw_by_branch = {b.id: request.POST.get(f"stock_{b.id}", "").strip() for b in branches_qs}

        # Se re-renderiza el form conservando lo que ya se había escrito, si hay que volver a mostrarlo.
        submitted_context = {
            **context,
            'name': name, 'sku': sku, 'unit': unit, 'selected_category': category_id,
            'cost_price': cost_price_raw, 'sale_price': sale_price_raw, 'min_stock': min_stock_raw,
            'stock_by_branch': stock_raw_by_branch,
        }

        errors = []

        if not name:
            errors.append("El nombre del producto es obligatorio.")
        if not sku:
            errors.append("El código (SKU) es obligatorio.")
        # exclude(id=product.id): que el propio producto no cuente como "duplicado" de sí mismo.
        if sku and Product.objects.filter(company=product.company, sku=sku).exclude(id=product.id).exists():
            errors.append("Ya existe un producto con ese código en esta empresa.")
        if not category_id:
            errors.append("Selecciona una categoría.")
        if not unit:
            errors.append("La unidad es obligatoria.")

        cost_price = sale_price = None
        if not cost_price_raw:
            errors.append("El precio de costo es obligatorio.")
        else:
            try:
                cost_price = Decimal(cost_price_raw)
                if cost_price <= 0:
                    errors.append("El precio de costo debe ser mayor a cero.")
            except InvalidOperation:
                errors.append("El precio de costo no es válido.")

        if not sale_price_raw:
            errors.append("El precio de venta es obligatorio.")
        else:
            try:
                sale_price = Decimal(sale_price_raw)
                if sale_price <= 0:
                    errors.append("El precio de venta debe ser mayor a cero.")
            except InvalidOperation:
                errors.append("El precio de venta no es válido.")

        if cost_price is not None and sale_price is not None and sale_price <= cost_price:
            errors.append("El precio de venta debe ser mayor al precio de costo.")

        min_stock = None
        if not min_stock_raw:
            errors.append("El stock mínimo es obligatorio.")
        elif not min_stock_raw.isdigit():
            errors.append("El stock mínimo debe ser un número entero.")
        elif int(min_stock_raw) < 5:
            errors.append("El stock mínimo no puede ser menor a 5.")
        else:
            min_stock = int(min_stock_raw)

        # Vacío = 0; si trae algo, tiene que ser un entero >= 0.
        stock_by_branch = {}
        for branch_id, raw in stock_raw_by_branch.items():
            if not raw:
                stock_by_branch[branch_id] = 0
            elif raw.isdigit():
                stock_by_branch[branch_id] = int(raw)
            else:
                errors.append("La cantidad de cada sucursal debe ser un número entero.")
                break

        if errors:
            messages.error(request, errors[0])
            return render(request, 'products/update_product.html', submitted_context)

        category_obj = get_object_or_404(Category, id=category_id)

        try:
            with transaction.atomic():
                product.name = name
                product.sku = sku
                product.unit = unit
                product.category = category_obj
                product.cost_price = cost_price
                product.sale_price = sale_price
                product.min_stock = min_stock
                product.full_clean()
                product.save()

                # Por sucursal: si ya existe el Stock se actualiza, si no existe se crea
                # (cubre sucursales que no tenían fila todavía, sean nuevas o de antes de cargar stock).
                for branch_id, quantity in stock_by_branch.items():
                    Stock.objects.update_or_create(
                        product=product, branch_id=branch_id, defaults={'quantity': quantity},
                    )
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar el producto. Inténtalo de nuevo.")
            return render(request, "products/update_product.html", submitted_context)

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"El producto {name} fue editado exitosamente.")

        # Aviso aparte (no bloquea el guardado) si alguna sucursal quedó en o por debajo del mínimo.
        low_branches = [branch_names[bid] for bid, qty in stock_by_branch.items() if qty <= min_stock]
        if low_branches:
            messages.warning(request, f"Quedó con stock bajo en: {', '.join(low_branches)}.")

        submitted_context['redirect_url'] = _product_list_url(request, product.company)
        return render(request, 'products/update_product.html', submitted_context)

    return render(request, 'products/update_product.html', context)

# Baja lógica (is_active=False): un producto no se borra nunca, tiene Movement/Stock asociados
# que forman el historial de inventario.
@login_required
@require_POST
@inventory_access_required
def deactivate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not request.user.is_platform_admin and product.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este producto.")
        return redirect('dashboard')
    product.is_active = False
    product.save()
    return redirect(_product_list_url(request, product.company))

@login_required
@require_POST
@inventory_access_required
def activate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not request.user.is_platform_admin and product.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este producto.")
        return redirect('dashboard')
    product.is_active = True
    product.save()
    return redirect(_product_list_url(request, product.company))
