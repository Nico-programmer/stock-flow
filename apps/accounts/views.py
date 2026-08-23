from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField
from django.shortcuts import render, redirect

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


""" Users List Wiew """
""" Users List View """
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