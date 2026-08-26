from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from django.contrib import messages

from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField

from django.shortcuts import render, redirect, get_object_or_404

from django.db import transaction, IntegrityError

# Import forms
from .forms import *

# Import models
from .models import *
from apps.companies.models import *

""" Login View """
def login_view(request):
    # If you are already authenticated, there is no point in seeing the login again.
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(request, "Tu cuenta está inactiva. Contacta al administrador.")
                    return render(request, 'login.html', {'form': form})

                login(request, user)

                # Redirection according to role
                if user.role == 'admin':
                    return redirect('dashboard')
                else:
                    return redirect('dashboard')
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
        # If the form is invalid, it lands here and is re-rendered with errors.
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


"""------------------------------------------------------------------ Users View ------------------------------------------------------------------"""

# User List
def userList_view(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    permission_filter = request.GET.get('permission', '')
 
    users = (
        CustomUser.objects
        .filter(company=request.user.company)
        .select_related('permissions')
    )
 
    if query:
        users = users.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )
 
    if role_filter:
        users = users.filter(role=role_filter)
 
    if permission_filter:
        # permission_filter llega como 'can_manage_inventory', 'can_manage_sales', etc.
        users = users.filter(**{f'permissions__{permission_filter}': True})
 
    # Orden fijo: Admin -> Encargado -> Empleado (no alfabético del value del choice)
    users = users.annotate(
        role_order=Case(
            When(role=CustomUser.Role.ADMIN, then=Value(0)),
            When(role=CustomUser.Role.MANAGER, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by('role_order', 'first_name', 'last_name')
 
    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
 
    context = {
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'permission_filter': permission_filter,
    }
    return render(request, "users/user_list.html", context)

# Create users
@login_required
def create_user(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        role = request.POST.get("role", "")

        # --- 1. Preliminary validations (without touching the database) ---
        errors = []

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
        if role not in ('manager', 'employee'):
            errors.append("Selecciona un rol válido.")
        if username and CustomUser.objects.filter(username=username).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        if email and CustomUser.objects.filter(email=email).exists():
            errors.append("Ese correo ya está registrado.")

        if errors:
            messages.error(request, errors[0])  # ← only the first one, not a for loop
            return render(request, 'users/create_users.html', {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'role': role
            })

        # --- 2. Creation within a transaction ---
        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    email = email,
                    username = username,
                    password = password,
                    first_name = first_name,
                    last_name = last_name,
                    company = request.user.company,
                    role = role
                )

                EmployeePermission.objects.filter(user = user).update(
                    can_manage_inventory='can_manage_inventory' in request.POST,
                    can_manage_sales='can_manage_sales' in request.POST,
                    can_manage_employees='can_manage_employees' in request.POST,
                    can_view_reports='can_view_reports' in request.POST,
                    granted_by=request.user,
                )
        except IntegrityError:
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html')

        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return render(request, 'users/create_users.html')
    return render(request, 'users/create_users.html')

@login_required
def update_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    permissions = EmployeePermission.objects.filter(user=employee).first()

    context = {"employee": employee, "permissions": permissions}

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "")

        # --- 1. Validaciones previas ---
        errors = []

        if not first_name:
            errors.append("El nombre es obligatorio.")
        if not last_name:
            errors.append("El apellido es obligatorio.")
        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        if not email:
            errors.append("El correo es obligatorio.")
        if role not in ('manager', 'employee'):
            errors.append("Selecciona un rol válido.")
        if CustomUser.objects.filter(username=username).exclude(id=employee.id).exists():
            errors.append("Ese nombre de usuario ya está en uso.")
        if CustomUser.objects.filter(email=email).exclude(id=employee.id).exists():
            errors.append("Ese correo ya está en uso.")

        if errors:
            messages.error(request, errors[0])
            return render(request, 'users/update_user.html', context)

        # --- 2. Actualización dentro de una transacción ---
        try:
            with transaction.atomic():
                employee.first_name = first_name
                employee.last_name = last_name
                employee.username = username
                employee.email = email
                employee.role = role
                employee.save()

                EmployeePermission.objects.filter(user=employee).update(
                    can_manage_inventory='can_manage_inventory' in request.POST,
                    can_manage_sales='can_manage_sales' in request.POST,
                    can_manage_employees='can_manage_employees' in request.POST,
                    can_view_reports='can_view_reports' in request.POST,
                    granted_by=request.user,
                )
        except IntegrityError:
            messages.error(request, "Ocurrió un error al actualizar el usuario. Inténtalo de nuevo.")
            return render(request, "users/update_user.html", context)

        messages.success(request, f"El usuario {username} fue editado exitosamente.")
        return redirect('users_list')

    return render(request, 'users/update_user.html', context)

# Desactive user
@login_required
@require_POST
def deactivate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)

    if employee.id == request.user.id:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return redirect("users_list")

    employee.is_active = False
    employee.save()

    messages.success(request, f"El usuario {employee.username} fue desactivado.")
    return redirect("users_list")

# Active user
@login_required
@require_POST
def activate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    employee.is_active = True
    employee.save()

    messages.success(request, f"El usuario {employee.username} fue reactivado.")
    return redirect("users_list")