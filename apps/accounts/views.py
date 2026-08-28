# authenticator
from django.contrib.auth import authenticate, login

# Decorators
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from .decorators import superuser_required

from django.contrib import messages

# Import paginator
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
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
@login_required
@superuser_required
def userList_view(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    permission_filter = request.GET.get('permission', '')
    company_filter = request.GET.get('company', '')

    users = (
        CustomUser.objects
        .select_related('permissions', 'company')  # The company name is added to avoid N+1 queries when displaying the name
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
        users = users.filter(**{f'permissions__{permission_filter}': True})

    if company_filter:
        # company_filter arrives as the id of the selected company
        users = users.filter(company_id=company_filter)

    # Order: first by company name (so that regroup works in the template),
    # then the fixed role order, then name
    users = users.annotate(
        role_order=Case(
            When(role=CustomUser.Role.ADMIN, then=Value(0)),
            When(role=CustomUser.Role.MANAGER, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by('company__name', 'role_order', 'first_name', 'last_name')

    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'permission_filter': permission_filter,
        'company_filter': company_filter,
        'companies': Company.objects.all(),  # to populate the <select> of the filter
    }
    return render(request, "users/user_list.html", context)

# Create users
@login_required
@superuser_required
def create_user(request):
    # Now you choose the branch, not the company.
    branches_qs = Branch.objects.filter(is_active=True)

    if request.method == "POST":
        branch_id = request.POST.get("branch", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        role = request.POST.get("role", "")

        errors = []

        if not branch_id:
            errors.append("Selecciona la sucursal a la que pertenece el usuario.")
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
            messages.error(request, errors[0])
            return render(request, 'users/create_users.html', {
                'branch': branches_qs,
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'role': role,
            })

        branch_obj = get_object_or_404(Branch, id=branch_id)

        try:
            with transaction.atomic():
                # The object is built WITHOUT saving yet (set_password + full_clean first)
                user = CustomUser(
                    email=CustomUser.objects.normalize_email(email),
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    branch=branch_obj,
                    role=role,
                )
                user.set_password(password)   # Hash the password before validating/saving
                user.full_clean()             # ← Here your clean() validation is executed
                user.save()                   # It is only here that it is saved in the database

                EmployeePermission.objects.filter(user=user).update(
                    can_manage_inventory='can_manage_inventory' in request.POST,
                    can_manage_sales='can_manage_sales' in request.POST,
                    can_manage_employees='can_manage_employees' in request.POST,
                    can_view_reports='can_view_reports' in request.POST,
                    granted_by=request.user,
                )
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html', {'branch': branches_qs})

        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return redirect('users_list')

    return render(request, 'users/create_users.html', {'branch': branches_qs})

@login_required
@superuser_required
def update_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    permissions = EmployeePermission.objects.filter(user=employee).first()
    companies_qs = Company.objects.all()  # different name to avoid conflicting with the POST

    context = {
        "employee": employee,
        "permissions": permissions,
        "company": companies_qs,
        "roles": CustomUser.Role.choices,  # [('admin', 'Administrador'), ('manager', 'Gerente'), ('employee', 'Empleado')],
    }

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "")

        # --- 1. Prior validations ---
        errors = []

        if not company_id:
            errors.append("Selecciona la compañía a la que pertenece el usuario.")
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

        # It is verified that the selected company actually exists
        company_obj = get_object_or_404(Company, id=company_id)

        # --- 2. Update within a transaction ---
        try:
            with transaction.atomic():
                employee.first_name = first_name
                employee.last_name = last_name
                employee.username = username
                employee.email = email
                employee.role = role
                employee.company = company_obj
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

        return redirect('users_list')

    return render(request, 'users/update_user.html', context)

# Desactive user
@login_required
@require_POST
@superuser_required
def deactivate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)

    if employee.id == request.user.id:
        return redirect("users_list")

    employee.is_active = False
    employee.save()

    return redirect("users_list")

# Active user
@login_required
@require_POST
@superuser_required
def activate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    employee.is_active = True
    employee.save()

    return redirect("users_list")