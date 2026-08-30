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

@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return render(request, "login.html", {'form': LoginForm, 'redirect_url': reverse('account:login')})

"""------------------------------------------------------------------ Users View ------------------------------------------------------------------"""

@login_required
@superuser_required
def userList_view(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    permission_filter = request.GET.get('permission', '')
    company_filter = request.GET.get('company', '')

    users = (
        CustomUser.objects
        .select_related('permissions', 'company', 'branch', 'branch__company')
        .annotate(
            # Si el usuario tiene company directa (admin), se usa esa.
            # Si no, se usa la company de su branch (manager/employee).
            effective_company_id=Case(
                When(company__isnull=False, then=F('company_id')),
                default=F('branch__company_id'),
                output_field=IntegerField(),
            )
        )
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
        users = users.filter(effective_company_id=company_filter)

    # Orden fijo por rol: Admin -> Encargado -> Empleado
    users = users.annotate(
        role_order=Case(
            When(role=CustomUser.Role.ADMIN, then=Value(0)),
            When(role=CustomUser.Role.MANAGER, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by('effective_company_id', 'role_order', 'first_name', 'last_name')

    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Agrupamiento manual por empresa (regroup no sirve aquí porque no hay
    # un campo FK directo "company" en todos los usuarios)
    grouped = []
    for company_id, group in groupby(page_obj.object_list, key=lambda u: u.effective_company_id):
        group_list = list(group)
        first_user = group_list[0]
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
    companies_qs = Company.objects.filter(is_active=True)
    roles = CustomUser.Role.choices

    if request.method == "POST":
        company_id = request.POST.get("company", "").strip()
        branch_id = request.POST.get("branch", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        role = request.POST.get("role", "")

        can_manage_inventory = 'can_manage_inventory' in request.POST
        can_manage_sales = 'can_manage_sales' in request.POST
        can_manage_employees = 'can_manage_employees' in request.POST
        can_view_reports = 'can_view_reports' in request.POST

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

        errors = []

        if not company_id:
            errors.append("Selecciona la empresa.")
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
            messages.error(request, errors[0])
            return render(request, 'users/create_users.html', base_context)

        try:
            with transaction.atomic():
                user = CustomUser(
                    email=CustomUser.objects.normalize_email(email),
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                )

                if role == 'admin':
                    company_obj = get_object_or_404(Company, id=company_id, is_active=True)
                    user.company = company_obj
                    user.branch = None
                else:
                    branch_obj = get_object_or_404(Branch, id=branch_id, company_id=company_id, is_active=True)
                    user.branch = branch_obj
                    user.company = None

                user.set_password(password)
                user.full_clean()
                user.save()

                # El admin no maneja EmployeePermission, tiene acceso total por rol
                if role != 'admin':
                    EmployeePermission.objects.update_or_create(
                        user=user,
                        defaults={
                            'branch': user.branch,
                            'can_manage_inventory': can_manage_inventory,
                            'can_manage_sales': can_manage_sales,
                            'can_manage_employees': can_manage_employees,
                            'can_view_reports': can_view_reports,
                            'granted_by': request.user,
                        }
                    )
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al crear al usuario. Intenta de nuevo.")
            return render(request, 'users/create_users.html', base_context)

        messages.success(request, f"Usuario {user.username} creado correctamente.")
        return render(request, 'users/create_users.html', {
            'companies': companies_qs,
            'roles': roles,
            'redirect_url': reverse('account:list'),
        })

    return render(request, 'users/create_users.html', {'companies': companies_qs, 'roles': roles})

@login_required
@superuser_required
def update_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    permissions = EmployeePermission.objects.filter(user=employee).first()
    companies_qs = Company.objects.filter(is_active=True)

    # La empresa actual del empleado puede venir de dos lados según su rol:
    # admin -> employee.company ; manager/employee -> employee.branch.company
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
                    # Si el usuario pasó de manager/employee a admin, se limpia cualquier permiso residual
                    EmployeePermission.objects.filter(user=employee).delete()
        except (IntegrityError, ValidationError):
            messages.error(request, "Ocurrió un error al actualizar el usuario. Inténtalo de nuevo.")
            return render(request, "users/update_user.html", context)

        messages.success(request, f"El usuario {username} fue editado exitosamente.")
        context['redirect_url'] = reverse('account:list')

    return render(request, 'users/update_user.html', context)

# Desactive user
@login_required
@require_POST
@superuser_required
def deactivate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)

    if employee.id == request.user.id:
        return redirect("account:list")

    employee.is_active = False
    employee.save()

    return redirect("account:list")

# Active user
@login_required
@require_POST
@superuser_required
def activate_user(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)
    employee.is_active = True
    employee.save()

    return redirect("account:list")