from django.shortcuts import render, redirect, get_object_or_404

# Import models
from .models import *

# Import decorators
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import superuser_required
from django.http import JsonResponse

# Import paginator's
from django.core.paginator import Paginator
from django.db.models import Q

# Import messages
from django.contrib import messages

# Import transaction
from django.db import transaction, IntegrityError

# Endpoint AJAX: lo llama el JS del form de usuarios al cambiar el <select> de empresa,
# para repoblar el <select> de sucursal con las sucursales activas de esa empresa.
@login_required
@superuser_required
def get_branches_by_company(request, company_id):
    """Devuelve las sucursales activas de una empresa, en formato JSON, para el <select> dinámico."""
    branches = Branch.objects.filter(company_id=company_id, is_active=True).values('id', 'name')
    # safe=False: permite serializar una lista (no solo un dict) como cuerpo JSON.
    return JsonResponse(list(branches), safe=False)

# Detalle de una empresa y sus sucursales.
@login_required
def company_info(request, company_id):
    # OJO: falta el nombre del lookup -> debería ser get_object_or_404(Company, id=company_id).
    company = get_object_or_404(Company, company_id)
    branch = Branch.objects.filter(company=company_id)

    context = {'company': company, 'branch': branch}
    return render(request, "companies/company_info.html", context)

# Listado de empresas con búsqueda, filtro por estado y paginación.
@login_required
@superuser_required
def companies_list(request):
    # Parámetros que llegan por querystring (?q=...&status=...).
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '') # 'active' / 'inactive' / ''

    companies = Company.objects.all()

    if query:
        # Busca en el nombre de la empresa, en la dirección de cualquiera de sus sucursales
        # y en el teléfono. El JOIN a branches puede devolver la misma empresa varias veces...
        companies = companies.filter(
            Q(name__icontains = query) |
            Q(branches__address__icontains = query) |
            Q(phone_number__icontains = query)
        ).distinct() # ...por eso distinct(): colapsa esos duplicados.

    if status_filter == 'active':
        companies = companies.filter(is_active=True)
    elif status_filter == 'inactive':
        companies = companies.filter(is_active=False)

    companies = companies.order_by('name')

    # Paginación: 10 por página, igual que el listado de usuarios. ?page=N elige la página.
    paginator = Paginator(companies, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
    }
    return render(request, "companies_list.html", context)

# Alta de una empresa junto con una o varias sucursales, en la misma transacción.
@login_required
@superuser_required
def create_companies(request):
    if request.method == 'POST':
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        is_active = "is_active" in request.POST

        # El form manda las sucursales como arrays (inputs name="branch_name[]" clonados por JS).
        # getlist() devuelve la lista completa de valores de ese name; los dos arrays van "en paralelo".
        branch_name = request.POST.getlist("branch_name[]")
        branch_addresses  = request.POST.getlist("branch_address[]")

        # --- 1. Validaciones (se juntan todas antes de tocar la BD) ---
        errors = []

        if not name:
            errors.append("El nombre es obligatorio.")
        if not phone:
            errors.append("El teléfono es obligatorio.")
        if name and Company.objects.filter(name=name).exists():
            errors.append("El nombre de la compañía ya existe.")

        # zip empareja nombre[i] con dirección[i]. Se descartan las filas totalmente vacías.
        valid_branches = [
            (n.strip(), a.strip())
            for n, a in zip(branch_name, branch_addresses)
            if n.strip() or a.strip()
        ]

        if not valid_branches:
            errors.append("Debes agregar al menos una sucursal.")
        else:
            # Si una fila tiene un dato, tiene que tener los dos (nombre y dirección).
            for n, a in valid_branches:
                if not n:
                    errors.append("Todas las sucursales deben tener un nombre.")
                    break
                if not a:
                    errors.append("Todas las sucursales deben tener una dirección.")
                    break

        if errors:
            messages.error(request, errors[0])

            # Se re-renderiza el form conservando lo que el usuario ya había escrito.
            return render(request, 'companies/create_companies.html', {
                'name': name,
                'branch_name': branch_name,
                'phone': phone,
                'address': branch_addresses,
                'is_active': is_active
            })

        # --- 2. Creación dentro de una transacción (empresa + sucursales, todo o nada) ---
        try:
            with transaction.atomic():
                company = Company.objects.create(
                    name = name,
                    phone_number = phone,
                    is_active = is_active
                )

                for b_name, b_address in valid_branches:
                    Branch.objects.create(
                        company = company,
                        name = b_name,
                        address = b_address,
                    )
        except IntegrityError:
            messages.error(request, 'Ocurrió un error al crear la empresa. Intenta de nuevo.')
            return render(request, 'companies/create_companies.html')

        return redirect('companies_list') # Post/Redirect/Get: evita reenviar el form si se recarga
    # GET: form vacío.
    return render(request, 'companies/create_companies.html')

# Edición de una empresa y de sus sucursales (existentes y nuevas) a la vez.
@login_required
@superuser_required
def update_companies(request, companies_id):
    company = get_object_or_404(Company, id=companies_id)
    branches = Branch.objects.filter(company=company)

    context = {'company': company, 'branches': branches}

    if request.method == 'POST':
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()

        # Tres arrays en paralelo. branch_id[] distingue sucursal existente (trae id) de nueva (vacío).
        branch_ids = request.POST.getlist("branch_id[]")
        branch_names = request.POST.getlist("branch_name[]")
        branch_addresses = request.POST.getlist("branch_address[]")

        # --- 1. Validaciones ---
        errors = []

        if not name:
            errors.append("El nombre es obligatorio.")
        if not phone:
            errors.append("El teléfono es obligatorio.")

        # Tiene que quedar al menos una sucursal completa; una fila a medias es error.
        has_valid_branch = False
        for b_name, b_address in zip(branch_names, branch_addresses):
            if b_name.strip() and b_address.strip():
                has_valid_branch = True
            elif b_name.strip() or b_address.strip():
                errors.append("Cada sucursal debe tener nombre y dirección.")
                break

        if not has_valid_branch:
            errors.append("Debes tener al menos una sucursal completa.")

        if errors:
            messages.error(request, errors[0])
            return render(request, "companies/update_companies.html", context)

        # --- 2. Actualización dentro de una transacción ---
        try:
            with transaction.atomic():
                company.name = name
                company.phone_number = phone
                company.save()

                # Se recorren las tres listas en paralelo (id, nombre, dirección de cada fila).
                for b_id, b_name, b_address in zip(branch_ids, branch_names, branch_addresses):
                    b_name = b_name.strip()
                    b_address = b_address.strip()

                    if not b_name and not b_address:
                        continue # fila vacía: se ignora

                    if b_id:
                        # Fila con id -> sucursal existente: se actualiza. company=company evita
                        # editar por error una sucursal de otra empresa si mandan un id ajeno.
                        Branch.objects.filter(id=b_id, company=company).update(
                            name=b_name,
                            address=b_address,
                        )
                    else:
                        # Fila sin id -> sucursal nueva: se crea.
                        Branch.objects.create(
                            company=company,
                            name=b_name,
                            address = b_address
                        )
        except IntegrityError:
            messages.error(request, "Ocurrió un error al actualizar la empresa. Intenta de nuevo.")
            return render(request, "companies/update_companies.html", context)

        return redirect('company:list')
    return render(request, "companies/update_companies.html", context)

# Reactiva una sucursal puntual y vuelve a la pantalla de edición de su empresa.
# El front lo dispara con fetch() (no con un <form>, para no anidar formularios en el form de edición).
@login_required
@superuser_required
def active_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_active = True
    branch.save()
    return redirect('company:update', companies_id=branch.company_id)

# Baja lógica de una sucursal puntual (mismo flujo que active_branch).
@login_required
@superuser_required
def inactive_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_active = False
    branch.save()
    return redirect('company:update', companies_id=branch.company_id)