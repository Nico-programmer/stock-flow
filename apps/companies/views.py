from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

# Import models
from .models import *
from apps.accounts.models import User, Group, GroupTemplate

# Import decorators
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from apps.accounts.decorators import platform_admin_required
from django.http import JsonResponse

from django.db.models import Count, Q

# Import messages
from django.contrib import messages

# Import transaction
from django.db import transaction, IntegrityError

# Endpoint AJAX: lo llama el JS del form de usuarios al cambiar el <select> de empresa,
# para repoblar el <select> de sucursal con las sucursales activas de esa empresa.
@login_required
@platform_admin_required
def get_branches_by_company(request, company_id):
    """Devuelve las sucursales activas de una empresa, en formato JSON, para el <select> dinámico."""
    branches = Branch.objects.filter(company_id=company_id, is_active=True).values('id', 'name')
    # safe=False: permite serializar una lista (no solo un dict) como cuerpo JSON.
    return JsonResponse(list(branches), safe=False)

# El Gerente General (usuario de empresa, sin sucursal: request.user.branch_id is None) puede
# administrar las sucursales de SU PROPIA empresa, igual que el admin de plataforma con cualquiera.
# Un empleado con una sucursal asignada NO entra acá aunque tenga can_access_users: gestionar
# sucursales es cosa del dueño, no de cualquiera con acceso a usuarios.
def _can_manage_branches(request, company):
    if request.user.is_platform_admin:
        return True
    return request.user.company_id == company.id and request.user.branch_id is None

# Detalle de una empresa y sus sucursales.
# Sin company_id: cada usuario ve SU PROPIA empresa (request.user.company).
# Con company_id: solo el admin de plataforma, para ver cualquier empresa desde companies_list.
@login_required
def company_info(request, company_id=None):
    if company_id is not None:
        if not request.user.is_platform_admin:
            messages.error(request, "No tienes permiso para ver esta empresa.")
            return redirect('dashboard')
        company = get_object_or_404(Company, id=company_id)
    else:
        if request.user.is_platform_admin:
            messages.error(request, "Selecciona una empresa desde el listado.")
            return redirect('company:list')
        company = request.user.company

    # active_employees_count: cuántos empleados ACTIVOS quedarían "huérfanos" si se desactiva
    # esa sucursal (ver branch_deactivate_review). Solo cuenta los activos: uno ya desactivado
    # no importa para esta decisión.
    branches = company.branches.annotate(
        active_employees_count=Count('users', filter=Q(users__is_active=True))
    ).order_by('name')

    context = {
        'company': company,
        'branches': branches,
        'can_manage_branches': _can_manage_branches(request, company),
    }
    return render(request, "companies/company_info.html", context)

# Alta de una sucursal para la propia empresa (Gerente General) o cualquiera (admin, con company_id).
@login_required
def create_branch(request, company_id=None):
    if company_id is not None:
        company = get_object_or_404(Company, id=company_id)
    else:
        company = request.user.company

    if company is None or not _can_manage_branches(request, company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    context = {'company': company}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        address = request.POST.get("address", "").strip()

        submitted_context = {**context, 'name': name, 'address': address}

        errors = []
        if not name:
            errors.append("El nombre de la sucursal es obligatorio.")
        if name and Branch.objects.filter(company=company, name=name).exists():
            errors.append("Ya existe una sucursal con ese nombre en esta empresa.")

        if errors:
            messages.error(request, errors[0])
            return render(request, "companies/create_branch.html", submitted_context)

        try:
            Branch.objects.create(company=company, name=name, address=address)
        except IntegrityError:
            messages.error(request, "Ocurrió un error al crear la sucursal. Inténtalo de nuevo.")
            return render(request, "companies/create_branch.html", submitted_context)

        messages.success(request, f"Sucursal {name} creada correctamente.")
        redirect_url = reverse('company:info', args=[company.id]) if request.user.is_platform_admin else reverse('company:info')
        return render(request, "companies/create_branch.html", {'company': company, 'redirect_url': redirect_url})

    return render(request, "companies/create_branch.html", context)

# Edición de nombre/dirección de una sucursal existente.
@login_required
def update_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    company = branch.company

    if not _can_manage_branches(request, company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    context = {'company': company, 'branch': branch}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        address = request.POST.get("address", "").strip()

        submitted_context = {**context, 'name': name, 'address': address}

        errors = []
        if not name:
            errors.append("El nombre de la sucursal es obligatorio.")
        if name and Branch.objects.filter(company=company, name=name).exclude(id=branch.id).exists():
            errors.append("Ya existe una sucursal con ese nombre en esta empresa.")

        if errors:
            messages.error(request, errors[0])
            return render(request, "companies/update_branch.html", submitted_context)

        try:
            branch.name = name
            branch.address = address
            branch.save()
        except IntegrityError:
            messages.error(request, "Ocurrió un error al actualizar la sucursal. Inténtalo de nuevo.")
            return render(request, "companies/update_branch.html", submitted_context)

        messages.success(request, f"Sucursal {name} actualizada correctamente.")
        redirect_url = reverse('company:info', args=[company.id]) if request.user.is_platform_admin else reverse('company:info')
        return render(request, "companies/update_branch.html", {'company': company, 'branch': branch, 'redirect_url': redirect_url})

    return render(request, "companies/update_branch.html", context)

# Listado de empresas. Busqueda / orden / filtro por estado / paginacion: DataTables (cliente).
@login_required
@platform_admin_required
def companies_list(request):
    companies = (
        Company.objects
        .annotate(branch_count=Count('branches'))
        .order_by('name')
    )
    return render(request, "companies_list.html", {'companies': companies})

# Alta de una empresa junto con una o varias sucursales, en la misma transacción.
@login_required
@platform_admin_required
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

        # Filas ya escritas, para repoblar el form si hay que re-renderizarlo (ver abajo).
        submitted_branches = [{'name': n, 'address': a} for n, a in zip(branch_name, branch_addresses)]

        if errors:
            messages.error(request, errors[0])

            # Se re-renderiza el form conservando lo que el usuario ya había escrito.
            return render(request, 'companies/create_companies.html', {
                'name': name,
                'phone': phone,
                'is_active': is_active,
                'branches': submitted_branches,
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

                # Asigna todas las plantillas a la empresa nueva (Group = link a la plantilla, no
                # una copia), para no tener que asignarlas a mano cada vez (ver accounts.GroupTemplate).
                for template in GroupTemplate.objects.all():
                    Group.objects.create(company=company, template=template)
        except IntegrityError:
            messages.error(request, 'Ocurrió un error al crear la empresa. Intenta de nuevo.')
            return render(request, 'companies/create_companies.html', {
                'name': name,
                'phone': phone,
                'is_active': is_active,
                'branches': submitted_branches,
            })

        return redirect('company:list') # Post/Redirect/Get: evita reenviar el form si se recarga
    # GET: form vacío.
    return render(request, 'companies/create_companies.html')

# Edición de una empresa y de sus sucursales (existentes y nuevas) a la vez.
@login_required
@platform_admin_required
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

        # Filas ya escritas, para repoblar el form si hay que re-renderizarlo (ver abajo).
        # Los mismos campos (id/name/address/is_active) que trae `branches` en el GET, así el
        # template no necesita distinguir entre una sucursal ya guardada y una recién tipeada.
        branches_by_id = {str(b.id): b for b in branches}
        submitted_branches = [
            {
                'id': b_id, 'name': b_name, 'address': b_address,
                'is_active': branches_by_id[b_id].is_active if b_id in branches_by_id else True,
            }
            for b_id, b_name, b_address in zip(branch_ids, branch_names, branch_addresses)
        ]
        submitted_context = {**context, 'name': name, 'phone': phone, 'branches': submitted_branches}

        if errors:
            messages.error(request, errors[0])
            return render(request, "companies/update_companies.html", submitted_context)

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
            return render(request, "companies/update_companies.html", submitted_context)

        return redirect('company:list')
    return render(request, "companies/update_companies.html", context)

# Reactiva una sucursal puntual: admin de plataforma (cualquiera) o el Gerente General (la suya).
@login_required
def active_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _can_manage_branches(request, branch.company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    branch.is_active = True
    branch.save()
    messages.success(request, f"Sucursal {branch.name} reactivada correctamente.")

    if request.user.is_platform_admin:
        return redirect('company:update', companies_id=branch.company_id)
    return redirect('company:info')

# Baja lógica de una sucursal puntual (mismo flujo que active_branch).
@login_required
def inactive_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _can_manage_branches(request, branch.company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    branch.is_active = False
    branch.save()
    messages.success(request, f"Sucursal {branch.name} desactivada correctamente.")

    if request.user.is_platform_admin:
        return redirect('company:update', companies_id=branch.company_id)
    return redirect('company:info')

# Paso intermedio cuando la sucursal a desactivar TODAVÍA tiene empleados activos asignados:
# en vez de desactivarla y dejarlos "huérfanos" en silencio (ver _allowed_branches en
# inventory/views.py: su alcance de sucursales quedaría vacío), se le pregunta a quien la
# desactiva qué hacer con ellos. Si ya no tiene empleados, el botón de la tabla ni pasa por acá.
@login_required
def branch_deactivate_review(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _can_manage_branches(request, branch.company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    employees = User.objects.filter(branch=branch, is_active=True).order_by('username')
    if not employees.exists():
        # Ya no tiene empleados (se resolvió entre que cargó la página y este click): no hace
        # falta el paso intermedio, se desactiva directo.
        return redirect('company:inactive_branch', branch_id=branch.id)

    other_branches = branch.company.branches.filter(is_active=True).exclude(id=branch.id).order_by('name')

    return render(request, "companies/branch_deactivate_review.html", {
        'branch': branch, 'company': branch.company,
        'employees': employees, 'other_branches': other_branches,
    })

# Ejecuta la decisión tomada en branch_deactivate_review: reasignar a cada empleado a otra
# sucursal (o dejarlo sin sucursal) o desactivarlos junto con la sucursal. Todo o nada.
@login_required
@require_POST
def branch_deactivate_process(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _can_manage_branches(request, branch.company):
        messages.error(request, "No tienes permiso para administrar las sucursales de esta empresa.")
        return redirect('dashboard')

    action = request.POST.get("action", "").strip()
    employees = User.objects.filter(branch=branch, is_active=True)

    if action == "reassign":
        with transaction.atomic():
            for employee in employees:
                new_branch_id = request.POST.get(f"new_branch_{employee.id}", "").strip()
                # get_object_or_404(..., company=branch.company): no deja mandar a mano el id
                # de una sucursal de otra empresa.
                new_branch = get_object_or_404(Branch, id=new_branch_id, company=branch.company) if new_branch_id else None
                employee.branch = new_branch
                employee.save()

            branch.is_active = False
            branch.save()

        messages.success(request, f"Sucursal {branch.name} desactivada. Se reasignaron {employees.count()} empleado(s).")

    elif action == "deactivate_employees":
        with transaction.atomic():
            count = employees.update(is_active=False)
            branch.is_active = False
            branch.save()

        messages.warning(request, f"Sucursal {branch.name} desactivada junto con {count} empleado(s), que ya no pueden iniciar sesión.")

    else:
        messages.error(request, "Selecciona qué hacer con los empleados de la sucursal.")
        return redirect('company:branch_deactivate_review', branch_id=branch.id)

    if request.user.is_platform_admin:
        return redirect('company:update', companies_id=branch.company_id)
    return redirect('company:info')