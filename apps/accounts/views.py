# authenticator
from django.contrib.auth import authenticate, login, logout

# Decorators
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .decorators import platform_admin_required
from django.urls import reverse

from django.contrib import messages

from django.core.exceptions import ValidationError
from django.http import JsonResponse

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
@platform_admin_required
def userList_view(request):
    # Lista de todos los usuarios, de todas las empresas. Los admin de plataforma van primero
    # (-is_platform_admin: True antes que False). Busqueda/orden/paginacion: DataTables en el cliente.
    users = (
        User.objects
        .select_related('company', 'group')
        .order_by('-is_platform_admin', 'company__name', 'username')
    )
    return render(request, "users/user_list.html", {'users': users})

# Endpoint AJAX: lo llama el JS del form de usuarios al cambiar el <select> de empresa,
# para repoblar el <select> de grupo con los grupos de esa empresa.
@login_required
@platform_admin_required
def get_groups_by_company(request, company_id):
    groups = Group.objects.filter(company_id=company_id).values('id', 'name')
    return JsonResponse(list(groups), safe=False)

@login_required
@platform_admin_required
def create_user(request):
    # Alta de usuario. El form elige Empresa -> Grupo en cascada (el grupo se puebla por AJAX).

    companies_qs = Company.objects.filter(is_active=True)

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        group_id = request.POST.get("group", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # Contexto para re-renderizar el form con lo ya cargado si hay errores de validación.
        base_context = {
            'companies': companies_qs,
            'full_name': full_name,
            'username': username,
            'phone_number': phone_number,
            'selected_company': company_id,
            'selected_group': group_id,
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

        if errors:
            messages.error(request, errors[0])   # se muestra solo el primer error
            return render(request, 'users/create_users.html', base_context)

        try:
            with transaction.atomic():
                company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                # El grupo es opcional: un usuario puede quedar "sin grupo" hasta que se le asigne uno.
                group_obj = get_object_or_404(Group, id=group_id, company=company_obj) if group_id else None

                user = User.objects.create_user(
                    username=username,
                    password=password,
                    full_name=full_name,
                    phone_number=phone_number,
                    company=company_obj,
                    group=group_obj,
                )
        except (IntegrityError, ValidationError):
            # IntegrityError: choque de unique en BD. ValidationError: falla de full_clean().
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html', base_context)

        # Éxito: se re-renderiza con redirect_url para el SweetAlert (no redirect() directo).
        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return render(request, 'users/create_users.html', {
            'companies': companies_qs,
            'redirect_url': reverse('account:list'),
        })

    # GET: form vacío.
    return render(request, 'users/create_users.html', {'companies': companies_qs})

@login_required
@platform_admin_required
def update_user(request, user_id):
    # Edición de un usuario existente. Misma mecánica que create_user (empresa/grupo en cascada).

    employee = get_object_or_404(User, id=user_id)
    companies_qs = Company.objects.filter(is_active=True)

    context = {
        "employee": employee,
        "companies": companies_qs,
    }

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        group_id = request.POST.get("group", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()

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

        if errors:
            messages.error(request, errors[0])
            return render(request, 'users/update_user.html', context)

        try:
            with transaction.atomic():
                company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                group_obj = get_object_or_404(Group, id=group_id, company=company_obj) if group_id else None

                employee.full_name = full_name
                employee.username = username
                employee.phone_number = phone_number
                employee.company = company_obj
                employee.group = group_obj

                employee.full_clean()
                employee.save()
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
@platform_admin_required
def deactivate_user(request, user_id):
    employee = get_object_or_404(User, id=user_id)

    # El admin de plataforma no puede desactivarse a sí mismo (se quedaría afuera).
    if employee.id == request.user.id:
        return redirect("account:list")

    employee.is_active = False
    employee.save()

    return redirect("account:list")

# Reactiva un usuario dado de baja.
@login_required
@require_POST
@platform_admin_required
def activate_user(request, user_id):
    employee = get_object_or_404(User, id=user_id)
    employee.is_active = True
    employee.save()

    return redirect("account:list")

"""------------------------------------------------------------------ Groups View ------------------------------------------------------------------"""

@login_required
@platform_admin_required
def group_list(request):
    groups = Group.objects.select_related('company').order_by('company__name', 'name')
    return render(request, "groups/group_list.html", {'groups': groups})

@login_required
@platform_admin_required
def create_group(request):
    companies_qs = Company.objects.filter(is_active=True)

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        name = request.POST.get("name", "").strip()
        can_access_inventory = 'can_access_inventory' in request.POST
        can_access_sales = 'can_access_sales' in request.POST
        can_access_purchases = 'can_access_purchases' in request.POST
        can_access_users = 'can_access_users' in request.POST

        base_context = {
            'companies': companies_qs,
            'name': name,
            'selected_company': company_id,
            'can_access_inventory': can_access_inventory,
            'can_access_sales': can_access_sales,
            'can_access_purchases': can_access_purchases,
            'can_access_users': can_access_users,
        }

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if not name:
            errors.append("El nombre del grupo es obligatorio.")
        if company_id and name and Group.objects.filter(company_id=company_id, name=name).exists():
            errors.append("Ya existe un grupo con ese nombre en esta empresa.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'groups/create_group.html', base_context)

        company_obj = get_object_or_404(Company, id=company_id, is_active=True)
        Group.objects.create(
            company=company_obj,
            name=name,
            can_access_inventory=can_access_inventory,
            can_access_sales=can_access_sales,
            can_access_purchases=can_access_purchases,
            can_access_users=can_access_users,
        )

        # Éxito: NO se hace redirect() directo. Se re-renderiza el form con `redirect_url`
        # para que el template muestre el SweetAlert y navegue recién al cerrarlo.
        messages.success(request, f"Grupo {name} creado correctamente.")
        return render(request, 'groups/create_group.html', {
            'companies': companies_qs,
            'redirect_url': reverse('account:group_list'),
        })

    # GET: form vacío.
    return render(request, 'groups/create_group.html', {'companies': companies_qs})

@login_required
@platform_admin_required
def update_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    companies_qs = Company.objects.filter(is_active=True)

    context = {'group': group, 'companies': companies_qs}

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        name = request.POST.get("name", "").strip()

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
        if not name:
            errors.append("El nombre del grupo es obligatorio.")
        # exclude(id=group.id): que el propio grupo no cuente como "duplicado" de sí mismo.
        if Group.objects.filter(company_id=company_id, name=name).exclude(id=group.id).exists():
            errors.append("Ya existe un grupo con ese nombre en esta empresa.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'groups/update_group.html', context)

        try:
            with transaction.atomic():
                group.company = get_object_or_404(Company, id=company_id, is_active=True)
                group.name = name
                group.can_access_inventory = 'can_access_inventory' in request.POST
                group.can_access_sales = 'can_access_sales' in request.POST
                group.can_access_purchases = 'can_access_purchases' in request.POST
                group.can_access_users = 'can_access_users' in request.POST
                group.full_clean()
                group.save()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar el grupo. Inténtalo de nuevo.")
            return render(request, "groups/update_group.html", context)

        messages.success(request, f"El grupo {name} fue editado exitosamente.")
        return redirect('account:group_list')

    return render(request, 'groups/update_group.html', context)

# Elimina un grupo. Los usuarios que lo tenían quedan "sin grupo" (Group.on_delete=SET_NULL en User).
@login_required
@require_POST
@platform_admin_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return redirect('account:group_list')