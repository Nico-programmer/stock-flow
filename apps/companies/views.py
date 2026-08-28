from django.shortcuts import render, redirect

# Import models
from .models import *

# Import decorators
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import superuser_required

# Import paginator's
from django.core.paginator import Paginator
from django.db.models import Q

# Import messages
from django.contrib import messages

# Import transaction
from django.db import transaction, IntegrityError

# Companies list
@login_required
@superuser_required
def companies_list(request):
    # Search and filter parameters from the URL
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '') # 'active' / 'inactive' / ''

    companies = Company.objects.all()

    if query:
        companies = companies.filter(
            Q(name__icontains = query) |
            Q(address__icontains = query) |
            Q(phone_number__icontains = query)
        )

    if status_filter == 'active':
        companies = companies.filter(is_active=True)
    elif status_filter == 'inactive':
        companies = companies.filter(is_active=False)

    companies = companies.order_by('name')

    # Pagination (10 per page, same as in users_list)
    paginator = Paginator(companies, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
    }
    return render(request, "companies_list.html", context)

# Create companies
@login_required
@superuser_required
def create_companies(request):
    # Obtain companies
    companies = Company.objects.all()

    if request.method == 'POST':
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        is_active = request.POST.get("is_active", "")

        # --- 1. Preliminary validations (without touching the database) ---
        errors = []

        if not name:
            errors.append("El nombre es obligatorio.")
        elif not phone:
            errors.append("El número de teléfono es obligatorio.")
        elif not address:
            errors.append("La dirección es obligatorio.")
        elif name == companies.name:
            errors.append("El nombre de la compañia ya existe.")

        if errors:
            messages.error(request, errors[0])

            # The form is re-rendered with the existing text and the company queryset intact.
            return render(request, 'companies/create_companies.html', {
                'name': name,
                'phone': phone,
                'address': address,
                'is_active': is_active
            })

        # --- 2. Creation within a transaction ---
        try:
            with transaction.atomic():
                company = Company.objects.create(
                    name = name,
                    phone = phone,
                    address = address,
                    is_active = is_active
                )
        except IntegrityError:
            messages.error(request, 'Ocurrió un error al crear la empresa. Intenta de nuevo.')
            return render(request, 'companies/create_companies.html')

        return redirect('companies_list') # Post/Redirect/Get: avoids duplicate forwarding    
    return render(request, 'companies/create_companies.html')