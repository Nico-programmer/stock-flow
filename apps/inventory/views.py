from decimal import Decimal, InvalidOperation

from django.shortcuts import render,redirect, get_object_or_404

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.core.exceptions import ValidationError

from django.core.paginator import Paginator

from django.db.models import Q

from django.urls import reverse

from django.db import transaction, IntegrityError

from .models import *
from .utils import empresa_del_usuario, generar_sku_unico

# Inventario
@login_required
def inventory_list(request):
    return render(request, "inventory_list.html")

# Umbral de "stock bajo": a partir de acá el producto se marca en amarillo.
LOW_STOCK = 5

# Products
@login_required
def product_list(request):
    company = empresa_del_usuario(request.user)

    # Base: el superuser ve todos los productos; el resto, solo los de su empresa.
    if request.user.is_superuser:
        products = ProductModel.objects.select_related('company')
    else:
        products = ProductModel.objects.select_related('company').filter(company=company)

    # Filtros que llegan por querystring (?q=&brand=&status=&stock=&sort=).
    query = request.GET.get('q', '').strip()
    brand_filter = request.GET.get('brand', '')
    status_filter = request.GET.get('status', '')
    stock_filter = request.GET.get('stock', '')
    sort = request.GET.get('sort', 'name')

    # Busqueda de texto libre sobre codigo / nombre / marca.
    if query:
        products = products.filter(
            Q(sku__icontains=query) |
            Q(name__icontains=query) |
            Q(brand__icontains=query)
        )

    if brand_filter:
        products = products.filter(brand=brand_filter)

    # Estado activo/inactivo (baja logica).
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)

    # Estado de stock: sin stock / bajo / con stock.
    if stock_filter == 'out':
        products = products.filter(stock=0)
    elif stock_filter == 'low':
        products = products.filter(stock__gt=0, stock__lte=LOW_STOCK)
    elif stock_filter == 'in':
        products = products.filter(stock__gt=LOW_STOCK)

    # Orden: whitelist para no exponer un order_by arbitrario desde la URL.
    ordenes_validos = {'name', '-name', 'price', '-price', 'stock', '-stock', '-created_at'}
    if sort not in ordenes_validos:
        sort = 'name'
    products = products.order_by(sort)

    # Marcas existentes (para el <select>), dentro del alcance del usuario.
    marcas_base = ProductModel.objects.all() if request.user.is_superuser else ProductModel.objects.filter(company=company)
    brands = marcas_base.exclude(brand='').values_list('brand', flat=True).distinct().order_by('brand')

    # Paginacion: 15 por pagina.
    paginator = Paginator(products, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'company': company,
        'query': query,
        'brand_filter': brand_filter,
        'status_filter': status_filter,
        'stock_filter': stock_filter,
        'sort': sort,
        'brands': brands,
        'low_stock': LOW_STOCK,
    }
    return render(request, "products/product_list.html", context)

@login_required
def create_product(request):
    if request.method == 'POST':
        # La empresa sale del usuario logueado, NUNCA del POST (el input del form es solo visual).
        company = empresa_del_usuario(request.user)

        # Campos crudos del POST. El SKU no se pide: se autogenera mas abajo.
        name = request.POST.get("name", "").strip()
        brand = request.POST.get("brand", "").strip()
        price_raw = request.POST.get("price", "").strip()
        stock_raw = request.POST.get("stock", "").strip()

        # Contexto para re-renderizar el form conservando lo que el usuario ya cargo.
        base_context = {
            'name': name,
            'brand': brand,
            'price': price_raw,
            'stock': stock_raw,
        }

        # Se acumulan TODOS los checks primero; recien despues se toca la base de datos.
        errors = []

        if not company:
            errors.append("Tu usuario no tiene una empresa asignada.")
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

        # Stock: debe ser un entero >= 0.
        stock = None
        if not stock_raw:
            errors.append("El stock es obligatorio.")
        else:
            try:
                stock = int(stock_raw)
                if stock < 0:
                    errors.append("El stock debe ser mayor o igual a 0.")
            except ValueError:
                errors.append("El stock no es un numero valido.")

        # Nombre de la empresa para mostrarlo (fijo) en el form al re-renderizar.
        base_context['company_name'] = company.name if company else ""

        if errors:
            messages.error(request, errors[0])   # se muestra solo el primer error
            return render(request, "products/create_product.html", base_context)

        # SKU autogenerado: 12 caracteres (siempre >= 10), letras + numeros, unico por empresa.
        sku = generar_sku_unico(company)

        try:
            # atomic(): o se crea el producto entero o no se crea nada.
            with transaction.atomic():
                product = ProductModel(
                    company=company,
                    sku=sku,
                    name=name,
                    brand=brand,
                    price=price,
                    stock=stock,
                )
                product.full_clean()   # corre los validators del modelo (MinValueValidator, unique, etc.)
                product.save()
        except (IntegrityError, ValidationError):
            # IntegrityError: choque de unique en BD. ValidationError: falla de full_clean().
            messages.error(request, "Ocurrio un error al crear el producto. Intenta de nuevo.")
            return render(request, "products/create_product.html", base_context)

        # Exito: SweetAlert + redirect al listado (mismo patron que create_user).
        messages.success(request, f"Producto {product.name} creado correctamente.")
        return render(request, "products/create_product.html", {
            'redirect_url': reverse('inventory:create_product'),
        })

    # GET: form vacio, con el nombre de la empresa del usuario ya visible.
    company = empresa_del_usuario(request.user)
    return render(request, "products/create_product.html", {
        'company_name': company.name if company else "",
    })

@login_required
def update_product(request, product_id):
    product = get_object_or_404(ProductModel, id=product_id)

    context = {'product': product}
    return render(request, "products/update_product.html", context)

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