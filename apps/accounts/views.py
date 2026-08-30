# authenticator
from django.contrib.auth import authenticate, login, logout

# Decorators
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from .decorators import superuser_required
from django.urls import reverse

from django.contrib import messages

# Import paginator
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q, Case, When, Value, IntegerField, F
from itertools import groupby

from django.shortcuts import render, redirect, get_object_or_404

from django.db import transaction, IntegrityError

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

            if user is not None:
                # Cuenta dada de baja (soft delete): credenciales OK pero no se le deja entrar.
                if not user.is_active:
                    messages.error(request, "Tu cuenta está inactiva. Contacta al administrador.")
                    return render(request, 'login.html', {'form': form})

                login(request, user)  # crea la sesión

                # Éxito: NO se hace redirect() directo. Se re-renderiza el login con `redirect_url`
                # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
                messages.success(request, f"¡Bienvenido, {user.get_short_name()}!")
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
@superuser_required
def userList_view(request):
    # Lista de usuarios agrupada por empresa, con filtros y paginación.

    # Parámetros de filtro que llegan por querystring (?q=...&role=...&permission=...&company=...).
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    permission_filter = request.GET.get('permission', '')
    company_filter = request.GET.get('company', '')

    users = (
        CustomUser.objects
        # select_related: trae en el mismo query las relaciones que se usan al pintar la lista (evita N+1).
        .select_related('permissions', 'company', 'branch', 'branch__company')
        .annotate(
            # "Empresa efectiva" del usuario, sin importar el rol:
            #   admin            -> company_id directo
            #   manager/employee -> company_id de su sucursal
            # Se necesita como campo calculado para poder filtrar y agrupar por empresa de forma uniforme.
            effective_company_id=Case(
                When(company__isnull=False, then=F('company_id')),
                default=F('branch__company_id'),
                output_field=IntegerField(),
            )
        )
    )

    # Búsqueda de texto libre sobre nombre / usuario / email.
    if query:
        users = users.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    # permission_filter llega como nombre de campo ('can_manage_sales', ...); se arma el lookup dinámico
    # permissions__can_manage_sales=True. Solo matchea manager/employee (admin no tiene fila de permisos).
    if permission_filter:
        users = users.filter(**{f'permissions__{permission_filter}': True})

    # Filtra por empresa usando el campo calculado arriba.
    if company_filter:
        users = users.filter(effective_company_id=company_filter)

    # Orden final: primero por empresa, luego rol (Admin -> Gerente -> Empleado), luego nombre.
    # role_order es un campo calculado solo para poder ordenar por esa prioridad.
    users = users.annotate(
        role_order=Case(
            When(role=CustomUser.Role.ADMIN, then=Value(0)),
            When(role=CustomUser.Role.MANAGER, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by('effective_company_id', 'role_order', 'first_name', 'last_name')

    # Paginación: 10 por página. ?page=N elige la página.
    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Agrupamiento por empresa hecho en Python. No se usa {% regroup %} de Django porque este
    # requiere un atributo FK directo y acá la empresa es un campo calculado (effective_company_id).
    # groupby agrupa elementos CONSECUTIVOS -> depende de que el queryset ya venga ordenado por empresa.
    grouped = []
    for company_id, group in groupby(page_obj.object_list, key=lambda u: u.effective_company_id):
        group_list = list(group)
        first_user = group_list[0]
        # Se recupera el objeto Company real (para mostrar su nombre) desde el primer usuario del grupo.
        company_obj = first_user.company or (first_user.branch.company if first_user.branch else None)
        grouped.append({'company': company_obj, 'users': group_list})

    context = {
        'page_obj': page_obj,
        'grouped': grouped,
        'query': query,
        'role_filter': role_filter,
        'permission_filter': permission_filter,
        'company_filter': company_filter,
        'companies': Company.objects.filter(is_active=True),
    }
    return render(request, "users/user_list.html", context)

from django.urls import reverse

@login_required
@superuser_required
def create_user(request):
    # Alta de usuario. El form elige Empresa -> Sucursal en cascada (la sucursal se puebla por AJAX).

    companies_qs = Company.objects.filter(is_active=True)   # para el <select> de empresa
    roles = CustomUser.Role.choices                         # para el <select> de rol

    if request.method == "POST":
        # Se leen los campos crudos del POST (no se usa un ModelForm acá).
        company_id = request.POST.get("company", "").strip()
        branch_id = request.POST.get("branch", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        role = request.POST.get("role", "")

        # Checkboxes: si no se marcan, la key ni siquiera viene en el POST -> "x in request.POST".
        can_manage_inventory = 'can_manage_inventory' in request.POST
        can_manage_sales = 'can_manage_sales' in request.POST
        can_manage_employees = 'can_manage_employees' in request.POST
        can_view_reports = 'can_view_reports' in request.POST

        # Contexto para re-renderizar el form con lo ya cargado si hay errores de validación.
        base_context = {
            'companies': companies_qs,
            'roles': roles,
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'email': email,
            'selected_company': company_id,
            'selected_branch': branch_id,
            'selected_role': role,
            'can_manage_inventory': can_manage_inventory,
            'can_manage_sales': can_manage_sales,
            'can_manage_employees': can_manage_employees,
            'can_view_reports': can_view_reports,
        }

        # Se acumulan TODOS los checks primero; recién después se toca la base de datos.
        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        # La sucursal solo es obligatoria para manager/employee; el admin va contra la empresa.
        if role != 'admin' and not branch_id:
            errors.append("Selecciona la sucursal.")
        if not first_name:
            errors.append("El nombre es obligatorio.")
        if not last_name:
            errors.append("El apellido es obligatorio.")
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not email:
            errors.append("El correo electrónico es obligatorio.")
        if not password:
            errors.append("La contraseña es obligatoria.")
        if password != password2:
            errors.append("Las contraseñas no coinciden.")
        if role not in ('admin', 'manager', 'employee'):
            errors.append("Selecciona un rol válido.")
        if username and CustomUser.objects.filter(username=username).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        if email and CustomUser.objects.filter(email=email).exists():
            errors.append("Ese correo ya está registrado.")

        if errors:
            messages.error(request, errors[0])   # se muestra solo el primer error
            return render(request, 'users/create_users.html', base_context)

        try:
            # atomic(): usuario + permisos se crean juntos o no se crea nada.
            with transaction.atomic():
                user = CustomUser(
                    email=CustomUser.objects.normalize_email(email),
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                )

                # Vínculo con la organización según el rol (la otra FK se deja en None).
                if role == 'admin':
                    company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                    user.company = company_obj
                    user.branch = None
                else:
                    branch_obj = get_object_or_404(Branch, id=branch_id, company_id=company_id, is_active=True)
                    user.branch = branch_obj
                    user.company = None

                user.set_password(password)   # hashea la contraseña
                user.full_clean()             # dispara CustomUser.clean() (regla company/branch)
                user.save()

                # El admin NO tiene EmployeePermission: su acceso total sale del rol.
                # update_or_create: crea la fila o la actualiza si ya existía (más seguro que .update()).
                if role != 'admin':
                    EmployeePermission.objects.update_or_create(
                        user=user,
                        defaults={
                            'branch': user.branch,
                            'can_manage_inventory': can_manage_inventory,
                            'can_manage_sales': can_manage_sales,
                            'can_manage_employees': can_manage_employees,
                            'can_view_reports': can_view_reports,
                            'granted_by': request.user,   # queda registrado quién lo creó
                        }
                    )
        except (IntegrityError, ValidationError):
            # IntegrityError: choque de unique en BD. ValidationError: falla de full_clean().
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html', base_context)

        # Éxito: se re-renderiza con redirect_url para el SweetAlert (no redirect() directo).
        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return render(request, 'users/create_users.html', {
            'companies': companies_qs,
            'roles': roles,
            'redirect_url': reverse('account:list'),
        })

    # GET: form vacío.
    return render(request, 'users/create_users.html', {'companies': companies_qs, 'roles': roles})

@login_required
@superuser_required
def update_user(request, user_id):
    # Edición de un usuario existente. Misma mecánica que create_user (empresa/sucursal en cascada).

    employee = get_object_or_404(CustomUser, id=user_id)
    permissions = EmployeePermission.objects.filter(user=employee).first()   # None si es admin
    companies_qs = Company.objects.filter(is_active=True)

    # Empresa actual del usuario, para preseleccionar el <select>. Viene de company o de branch según rol.
    current_company_id = employee.company_id or (employee.branch.company_id if employee.branch else None)

    context = {
        "employee": employee,
        "permissions": permissions,
        "company": companies_qs,
        "roles": CustomUser.Role.choices,
        "current_company_id": current_company_id,
    }

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        branch_id = request.POST.get("branch", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "")

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if role != 'admin' and not branch_id:
            errors.append("Selecciona la sucursal a la que pertenece el usuario.")
        if not first_name:
            errors.append("El nombre es obligatorio.")
        if not last_name:
            errors.append("El apellido es obligatorio.")
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not email:
            errors.append("El correo es obligatorio.")
        if role not in ('admin', 'manager', 'employee'):
            errors.append("Selecciona un rol válido.")
        # exclude(id=employee.id): que el propio usuario no cuente como "duplicado" de sí mismo.
        if CustomUser.objects.filter(username=username).exclude(id=employee.id).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        if CustomUser.objects.filter(email=email).exclude(id=employee.id).exists():
            errors.append("Ese correo ya está en uso.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'users/update_user.html', context)

        try:
            with transaction.atomic():
                employee.first_name = first_name
                employee.last_name = last_name
                employee.username = username
                employee.email = email
                employee.role = role

                if role == 'admin':
                    company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                    employee.company = company_obj
                    employee.branch = None
                else:
                    branch_obj = get_object_or_404(Branch, id=branch_id, company_id=company_id, is_active=True)
                    employee.branch = branch_obj
                    employee.company = None

                employee.full_clean()
                employee.save()

                if role != 'admin':
                    # Crea o actualiza la fila de permisos con el estado de los checkboxes.
                    EmployeePermission.objects.update_or_create(
                        user=employee,
                        defaults={
                            'branch': employee.branch,
                            'can_manage_inventory': 'can_manage_inventory' in request.POST,
                            'can_manage_sales': 'can_manage_sales' in request.POST,
                            'can_manage_employees': 'can_manage_employees' in request.POST,
                            'can_view_reports': 'can_view_reports' in request.POST,
                            'granted_by': request.user,
                        }
                    )
                else:
                    # Pasó a admin: se borra su EmployeePermission (los admin no llevan).
                    EmployeePermission.objects.filter(user=employee).delete()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar el usuario. Inténtalo de nuevo.")
            return render(request, "users/update_user.html", context)

        # Éxito: redirect_url en el contexto para el SweetAlert; el render de abajo lo usa.
        messages.success(request, f"El usuario {username} fue editado exitosamente.")
        context['redirect_url'] = reverse('account:list')

    return render(request, 'users/update_user.html', context)

# Baja lógica de un usuario (is_active=False). @require_POST: solo por formulario con CSRF, nunca por link.
@login_required
@require_POST
@superuser_required
def deactivate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)

    # El superusuario no puede desactivarse a sí mismo (se quedaría afuera).
    if employee.id == request.user.id:
        return redirect("account:list")

    employee.is_active = False
    employee.save()

    return redirect("account:list")

# Reactiva un usuario dado de baja.
@login_required
@require_POST
@superuser_required
def activate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    employee.is_active = True
    employee.save()

    return redirect("account:list")