# authenticator
from django.contrib.auth import authenticate, login, logout

# Decorators
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .decorators import platform_admin_required, users_access_required
from django.urls import reverse

from django.contrib import messages

from django.core.exceptions import ValidationError
from django.http import JsonResponse

from django.shortcuts import render, redirect, get_object_or_404

from django.db import transaction, IntegrityError
from django.db.models import Case, When

# Import forms
from .forms import *

# Import models
from .models import *
from apps.companies.models import *

"""------------------------------------------------------------------ Authenticator Views ------------------------------------------------------------------"""

def login_view(request):
    # Si ya hay sesión, no tiene sentido mostrar el login.
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # authenticate() devuelve el usuario si las credenciales son válidas, o None.
            user = authenticate(request, username=username, password=password)

            if user is None:
                # ModelBackend rechaza usuarios inactivos en authenticate() sin distinguir el motivo,
                # así que si las credenciales son válidas pero está inactivo, lo verificamos aparte.
                inactive_user = User.objects.filter(username=username, is_active=False).first()
                if inactive_user is not None and inactive_user.check_password(password):
                    messages.error(request, "Tu cuenta está inactiva y no tiene acceso a la plataforma. Comunícate con la persona encargada de la gestión de usuarios en tu empresa para reactivarla.")
                    return render(request, 'login.html', {'form': form})

            if user is not None:
                login(request, user)  # crea la sesión

                # Éxito: NO se hace redirect() directo. Se re-renderiza el login con `redirect_url`
                # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
                messages.success(request, f"¡Bienvenido, {user.full_name or user.username}!")
                return render(request, 'login.html', {
                    'form': form,
                    'redirect_url': reverse('dashboard'),
                })
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})

# Reemplaza a LogoutView de Django para poder mostrar el SweetAlert antes de redirigir.
# @require_POST: Django 5+ ya no permite logout por GET; el botón debe ser un <form method="POST">.
@require_POST
def logout_view(request):
    logout(request)  # destruye la sesión
    messages.success(request, "Sesión cerrada correctamente.")
    # Mismo patrón que login: renderiza con redirect_url en vez de redirect() directo.
    return render(request, "login.html", {'form': LoginForm, 'redirect_url': reverse('account:login')})

"""------------------------------------------------------------------ Users View ------------------------------------------------------------------"""

@login_required
@users_access_required
def userList_view(request):
    # Admin de plataforma: todos los usuarios de todas las empresas (admin de plataforma primero).
    # Usuario de negocio con can_access_users: SOLO los empleados de su propia empresa.
    users = User.objects.select_related('company', 'group')
    # Grupos de gerencia primero (nombre de plantilla con "gerent"), después por fecha de alta.
    is_manager = Case(When(group__template__name__icontains='geren', then=0), default=1)
    if request.user.is_platform_admin:
        users = users.order_by('-is_platform_admin', 'company__name', is_manager, 'date_joined')
    else:
        users = users.filter(company_id=request.user.company_id).order_by(is_manager, 'date_joined')
    return render(request, "users/user_list.html", {'users': users})

# Endpoint AJAX: lo llama el JS del form de usuarios al cambiar el <select> de empresa,
# para repoblar el <select> de grupo con los grupos de esa empresa.
@login_required
@users_access_required
def get_groups_by_company(request, company_id):
    # Un usuario de negocio solo puede pedir los grupos de SU PROPIA empresa (nunca de otra).
    if not request.user.is_platform_admin and company_id != request.user.company_id:
        return JsonResponse([], safe=False)

    # 'name' es una property (delega a template.name), no un campo real: no se puede pedir
    # directo con .values(), hay que traer template__name y renombrarlo a mano.
    groups = Group.objects.filter(company_id=company_id).values(
        'id', 'template__name',
        'template__can_access_inventory', 'template__can_manage_inventory', 'template__can_access_movements',
        'template__can_access_users', 'template__can_access_reports',
    )
    data = [{
        'id': g['id'],
        'name': g['template__name'],
        # El front usa esto para preseleccionar el grupo de mayor acceso al crear un usuario nuevo
        # (el admin de plataforma solo da de alta al usuario "dueño" de la empresa).
        'full_access': all([
            g['template__can_access_inventory'], g['template__can_manage_inventory'], g['template__can_access_movements'],
            g['template__can_access_users'], g['template__can_access_reports'],
        ]),
    } for g in groups]
    return JsonResponse(data, safe=False)

# Endpoint AJAX: repuebla el <select> de sucursal al elegir/cargar la empresa (branch es opcional,
# vacío = usuario "de empresa" que ve todas las sucursales, ver User.branch en el modelo).
@login_required
@users_access_required
def get_branches_by_company(request, company_id):
    if not request.user.is_platform_admin and company_id != request.user.company_id:
        return JsonResponse([], safe=False)

    branches = Branch.objects.filter(company_id=company_id, is_active=True).values('id', 'name')
    return JsonResponse(list(branches), safe=False)

@login_required
@users_access_required
def create_user(request):
    # Alta de usuario. El form elige Empresa -> Grupo/Sucursal en cascada (se pueblan por AJAX).
    # Admin de plataforma: elige cualquier empresa activa. Usuario de negocio (can_access_users):
    # la empresa queda fija en la suya (nunca se lee del POST, así no hay forma de mandarla a mano).
    is_admin = request.user.is_platform_admin
    companies_qs = Company.objects.filter(is_active=True) if is_admin else Company.objects.filter(id=request.user.company_id, is_active=True)
    # GroupTemplate es global (no por empresa): se muestra en el panel de ayuda para que quien da
    # de alta sepa de un vistazo qué puede hacer cada grupo, sin tener que ir a mirarlo aparte.
    templates_qs = GroupTemplate.objects.order_by('name')

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip() if is_admin else str(request.user.company_id)
        group_id = request.POST.get("group", "").strip()
        branch_id = request.POST.get("branch", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # Contexto para re-renderizar el form con lo ya cargado si hay errores de validación.
        base_context = {
            'companies': companies_qs,
            'is_admin': is_admin,
            'templates': templates_qs,
            'full_name': full_name,
            'username': username,
            'phone_number': phone_number,
            'selected_company': company_id,
            'selected_group': group_id,
            'selected_branch': branch_id,
        }

        # Se acumulan TODOS los checks primero; recién después se toca la base de datos.
        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if not full_name:
            errors.append("El nombre completo es obligatorio.")
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not password:
            errors.append("La contraseña es obligatoria.")
        if password != password2:
            errors.append("Las contraseñas no coinciden.")
        if username and User.objects.filter(username=username).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        # Sin sucursal = usuario "de empresa" (ve todas). Eso solo lo puede dejar así el admin de
        # plataforma, que es quien da de alta al dueño de la empresa; un usuario de negocio dando
        # de alta a un empleado sí tiene que elegirle una sucursal puntual.
        if not is_admin and not branch_id:
            errors.append("Selecciona la sucursal del empleado.")

        if errors:
            messages.error(request, errors[0])   # se muestra solo el primer error
            return render(request, 'users/create_users.html', base_context)

        try:
            with transaction.atomic():
                company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                # Grupo y sucursal son opcionales: un usuario puede quedar "sin grupo" hasta que se
                # le asigne uno, y sin sucursal es un usuario "de empresa" (ve todas, ver User.branch).
                group_obj = get_object_or_404(Group, id=group_id, company=company_obj) if group_id else None
                branch_obj = get_object_or_404(Branch, id=branch_id, company=company_obj) if branch_id else None

                # is_platform_admin NUNCA se lee del POST: esta vista jamás da de alta un admin
                # de plataforma, ni aunque la llame un usuario de negocio con can_access_users.
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    full_name=full_name,
                    phone_number=phone_number,
                    company=company_obj,
                    group=group_obj,
                    branch=branch_obj,
                )
        except (IntegrityError, ValidationError):
            # IntegrityError: choque de unique en BD. ValidationError: falla de full_clean().
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html', base_context)

        # Éxito: se re-renderiza con redirect_url para el SweetAlert (no redirect() directo).
        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return render(request, 'users/create_users.html', {
            'companies': companies_qs, 'is_admin': is_admin, 'templates': templates_qs,
            'redirect_url': reverse('account:list'),
        })

    # GET: form vacío.
    return render(request, 'users/create_users.html', {
        'companies': companies_qs, 'is_admin': is_admin, 'templates': templates_qs,
    })

@login_required
@users_access_required
def update_user(request, user_id):
    # Edición de un usuario existente. Misma mecánica que create_user (empresa/grupo/sucursal en cascada).

    employee = get_object_or_404(User, id=user_id)
    is_admin = request.user.is_platform_admin

    # Un usuario de negocio (can_access_users) solo puede editar empleados de SU PROPIA empresa,
    # y nunca a un admin de plataforma (employee.company_id es None en ese caso, nunca calza).
    if not is_admin and employee.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este usuario.")
        return redirect('account:list')

    companies_qs = Company.objects.filter(is_active=True) if is_admin else Company.objects.filter(id=request.user.company_id, is_active=True)

    context = {
        "employee": employee,
        "companies": companies_qs,
        "is_admin": is_admin,
        # GroupTemplate es global: se muestra en el panel de ayuda para saber qué puede hacer cada grupo.
        "templates": GroupTemplate.objects.order_by('name'),
    }

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip() if is_admin else str(request.user.company_id)
        group_id = request.POST.get("group", "").strip()
        branch_id = request.POST.get("branch", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()

        # Se re-renderiza el form conservando lo que el admin ya había escrito, si hay que volver a mostrarlo.
        submitted_context = {
            **context,
            'full_name': full_name, 'username': username, 'phone_number': phone_number,
            'selected_company': company_id, 'selected_group': group_id, 'selected_branch': branch_id,
        }

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if not full_name:
            errors.append("El nombre completo es obligatorio.")
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        # exclude(id=employee.id): que el propio usuario no cuente como "duplicado" de sí mismo.
        if User.objects.filter(username=username).exclude(id=employee.id).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        # Mismo criterio que en create_user: un usuario de negocio no puede dejar a un empleado
        # sin sucursal (eso solo lo decide el admin de plataforma para el dueño de la empresa).
        if not is_admin and not branch_id:
            errors.append("Selecciona la sucursal del empleado.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'users/update_user.html', submitted_context)

        try:
            with transaction.atomic():
                company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                group_obj = get_object_or_404(Group, id=group_id, company=company_obj) if group_id else None
                branch_obj = get_object_or_404(Branch, id=branch_id, company=company_obj) if branch_id else None

                employee.full_name = full_name
                employee.username = username
                employee.phone_number = phone_number
                employee.company = company_obj
                employee.group = group_obj
                employee.branch = branch_obj

                employee.full_clean()
                employee.save()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar el usuario. Inténtalo de nuevo.")
            return render(request, "users/update_user.html", submitted_context)

        # Éxito: redirect_url en el contexto para el SweetAlert; el render de abajo lo usa.
        messages.success(request, f"El usuario {username} fue editado exitosamente.")
        context['redirect_url'] = reverse('account:list')

    return render(request, 'users/update_user.html', context)

# Baja lógica de un usuario (is_active=False). @require_POST: solo por formulario con CSRF, nunca por link.
@login_required
@require_POST
@users_access_required
def deactivate_user(request, user_id):
    employee = get_object_or_404(User, id=user_id)

    # Mismo límite que en update_user: un usuario de negocio no puede tocar cuentas de otra
    # empresa ni un admin de plataforma (company_id None en ese caso, nunca calza).
    if not request.user.is_platform_admin and employee.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este usuario.")
        return redirect("account:list")

    # Nadie puede desactivarse a sí mismo (se quedaría afuera).
    if employee.id == request.user.id:
        return redirect("account:list")

    # El Gerente General (usuario de empresa, sin sucursal) solo lo puede desactivar
    # un admin de plataforma, nunca otro empleado con permiso de Usuarios.
    if not request.user.is_platform_admin and not employee.branch_id:
        messages.error(request, "No puedes desactivar al Gerente General de la empresa.")
        return redirect("account:list")

    employee.is_active = False
    employee.save()

    messages.success(request, f"{employee.full_name} fue desactivado correctamente.")
    return redirect("account:list")

# Reactiva un usuario dado de baja.
@login_required
@require_POST
@users_access_required
def activate_user(request, user_id):
    employee = get_object_or_404(User, id=user_id)

    if not request.user.is_platform_admin and employee.company_id != request.user.company_id:
        messages.error(request, "No tienes permiso para editar este usuario.")
        return redirect("account:list")

    employee.is_active = True
    employee.save()

    messages.success(request, f"{employee.full_name} fue reactivado correctamente.")
    return redirect("account:list")

"""------------------------------------------------------------------ Groups View ------------------------------------------------------------------"""

@login_required
@platform_admin_required
def group_list(request):
    groups = Group.objects.select_related('company', 'template').order_by('company__name', 'template__name')

    companies_map = {}
    for group in groups:
        companies_map.setdefault(group.company, []).append(group)
    companies_data = [{'company': company, 'groups': group_list_} for company, group_list_ in companies_map.items()]

    return render(request, "groups/group_list.html", {'companies_data': companies_data})

# No hay "crear grupo" a mano: un Group es solo el link Empresa<->GroupTemplate, así que la
# única acción posible es asignar una plantilla existente a una empresa.
@login_required
@platform_admin_required
def assign_template(request):
    companies_qs = Company.objects.filter(is_active=True)
    templates_qs = GroupTemplate.objects.order_by('name')

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        template_ids = request.POST.getlist("templates")

        base_context = {
            'companies': companies_qs,
            'templates': templates_qs,
            'selected_company': company_id,
            'selected_templates': template_ids,
        }

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if not template_ids:
            errors.append("Selecciona al menos una plantilla.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'groups/assign_template.html', base_context)

        company_obj = get_object_or_404(Company, id=company_id, is_active=True)
        already_assigned = set(Group.objects.filter(company=company_obj, template_id__in=template_ids).values_list('template_id', flat=True))
        new_template_ids = [t for t in template_ids if int(t) not in already_assigned]

        if not new_template_ids:
            errors.append("Esa empresa ya tiene asignadas todas las plantillas seleccionadas.")
            messages.error(request, errors[0])
            return render(request, 'groups/assign_template.html', base_context)

        Group.objects.bulk_create([
            Group(company=company_obj, template_id=template_id) for template_id in new_template_ids
        ])

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"{len(new_template_ids)} plantilla(s) asignada(s) a {company_obj.name}.")
        return render(request, 'groups/assign_template.html', {
            'companies': companies_qs,
            'templates': templates_qs,
            'redirect_url': reverse('account:group_list'),
        })

    # GET: form vacío.
    return render(request, 'groups/assign_template.html', {'companies': companies_qs, 'templates': templates_qs})

# Edita de una vez todas las plantillas de una empresa: los checkboxes marcados quedan
# asignados y los que se desmarquen se quitan. Los usuarios de las plantillas quitadas
# quedan "sin grupo" (Group.on_delete=SET_NULL en User).
@login_required
@platform_admin_required
def edit_company_templates(request, company_id):
    company_obj = get_object_or_404(Company, id=company_id)
    templates_qs = GroupTemplate.objects.order_by('name')

    if request.method == "POST":
        template_ids = set(int(t) for t in request.POST.getlist("templates"))
        current_ids = set(Group.objects.filter(company=company_obj).values_list('template_id', flat=True))

        to_add = template_ids - current_ids
        to_remove = current_ids - template_ids

        Group.objects.bulk_create([Group(company=company_obj, template_id=template_id) for template_id in to_add])
        Group.objects.filter(company=company_obj, template_id__in=to_remove).delete()

        messages.success(request, f"Plantillas de {company_obj.name} actualizadas.")
        return render(request, 'groups/edit_company_templates.html', {
            'company': company_obj,
            'templates': templates_qs,
            'selected_templates': [str(t) for t in template_ids],
            'redirect_url': reverse('account:group_list'),
        })

    selected_templates = [str(t) for t in Group.objects.filter(company=company_obj).values_list('template_id', flat=True)]
    return render(request, 'groups/edit_company_templates.html', {
        'company': company_obj,
        'templates': templates_qs,
        'selected_templates': selected_templates,
    })

# Quita la asignación. Los usuarios que la tenían quedan "sin grupo" (Group.on_delete=SET_NULL en User).
@login_required
@require_POST
@platform_admin_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return redirect('account:group_list')

"""------------------------------------------------------------------ Group Templates View ------------------------------------------------------------------"""

@login_required
@platform_admin_required
def template_list(request):
    templates = GroupTemplate.objects.order_by('name')
    return render(request, "groups/template_list.html", {'templates': templates})

@login_required
@platform_admin_required
def create_template(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        can_access_inventory = 'can_access_inventory' in request.POST
        can_manage_inventory = 'can_manage_inventory' in request.POST
        can_access_movements = 'can_access_movements' in request.POST
        can_access_users = 'can_access_users' in request.POST
        can_access_reports = 'can_access_reports' in request.POST

        base_context = {
            'name': name,
            'can_access_inventory': can_access_inventory,
            'can_manage_inventory': can_manage_inventory,
            'can_access_movements': can_access_movements,
            'can_access_users': can_access_users,
            'can_access_reports': can_access_reports,
        }

        errors = []

        if not name:
            errors.append("El nombre de la plantilla es obligatorio.")
        if name and GroupTemplate.objects.filter(name=name).exists():
            errors.append("Ya existe una plantilla con ese nombre.")
        # Administrar sin poder ver no tiene sentido (ver models.GroupTemplate).
        if can_manage_inventory and not can_access_inventory:
            errors.append("Administrar inventario requiere también el permiso de verlo.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'groups/create_template.html', base_context)

        GroupTemplate.objects.create(
            name=name,
            can_access_inventory=can_access_inventory,
            can_manage_inventory=can_manage_inventory,
            can_access_movements=can_access_movements,
            can_access_users=can_access_users,
            can_access_reports=can_access_reports,
        )

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"Plantilla {name} creada correctamente.")
        return render(request, 'groups/create_template.html', {
            'redirect_url': reverse('account:template_list'),
        })

    # GET: form vacío.
    return render(request, 'groups/create_template.html')

@login_required
@platform_admin_required
def update_template(request, template_id):
    template = get_object_or_404(GroupTemplate, id=template_id)
    # 'name'/'can_access_*' van siempre planos (no vía template.foo): así el template HTML
    # no distingue entre valores recién cargados de la BD (GET) y los que el admin ya escribió (POST con error).
    context = {
        'template': template, 'name': template.name,
        'can_access_inventory': template.can_access_inventory, 'can_manage_inventory': template.can_manage_inventory,
        'can_access_movements': template.can_access_movements,
        'can_access_users': template.can_access_users, 'can_access_reports': template.can_access_reports,
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        can_access_inventory = 'can_access_inventory' in request.POST
        can_manage_inventory = 'can_manage_inventory' in request.POST
        can_access_movements = 'can_access_movements' in request.POST
        can_access_users = 'can_access_users' in request.POST
        can_access_reports = 'can_access_reports' in request.POST

        # Se re-renderiza el form conservando lo que el admin ya había escrito, si hay que volver a mostrarlo.
        submitted_context = {
            **context, 'name': name,
            'can_access_inventory': can_access_inventory, 'can_manage_inventory': can_manage_inventory,
            'can_access_movements': can_access_movements,
            'can_access_users': can_access_users, 'can_access_reports': can_access_reports,
        }

        errors = []

        if not name:
            errors.append("El nombre de la plantilla es obligatorio.")
        # exclude(id=template.id): que la propia plantilla no cuente como "duplicada" de sí misma.
        if GroupTemplate.objects.filter(name=name).exclude(id=template.id).exists():
            errors.append("Ya existe una plantilla con ese nombre.")
        if can_manage_inventory and not can_access_inventory:
            errors.append("Administrar inventario requiere también el permiso de verlo.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'groups/update_template.html', submitted_context)

        try:
            template.name = name
            template.can_access_inventory = can_access_inventory
            template.can_manage_inventory = can_manage_inventory
            template.can_access_movements = can_access_movements
            template.can_access_users = can_access_users
            template.can_access_reports = can_access_reports
            template.full_clean()
            template.save()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar la plantilla. Inténtalo de nuevo.")
            return render(request, "groups/update_template.html", submitted_context)

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"La plantilla {name} fue editada exitosamente.")
        context['redirect_url'] = reverse('account:template_list')

    return render(request, 'groups/update_template.html', context)

# Elimina una plantilla. CASCADE: se borran también todos los Group que la tenían asignada
# (en cualquier empresa), y los usuarios que estaban en esos grupos quedan sin grupo (SET_NULL).
@login_required
@require_POST
@platform_admin_required
def delete_template(request, template_id):
    template = get_object_or_404(GroupTemplate, id=template_id)
    template.delete()
    return redirect('account:template_list')