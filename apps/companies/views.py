from django.shortcuts import render, redirect

# Import models
from .models import *

# Import decorators
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import superuser_required
from django.shortcuts import render, get_object_or_404

# Import paginator's
from django.core.paginator import Paginator
from django.db.models import Q

# Import messages
from django.contrib import messages

# Import transaction
from django.db import transaction, IntegrityError

# Company info
@login_required
def company_info(request, company_id):
    company = get_object_or_404(Company, company_id)
    branch = Branch.objects.filter(company=company_id)

    context = {'company': company, 'branch': branch}
    return render(request, "companies/company_info.html", context)

# Companies list/Branch list
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
            Q(branches__address__icontains = query) |
            Q(phone_number__icontains = query)
        ).distinct() # Required: Without this, a company with multiple matching branches appears duplicated

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

# Create companies/branch
@login_required
@superuser_required
def create_companies(request):
    if request.method == 'POST':
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        is_active = "is_active" in request.POST

        # getlist() returns a list with all the values ​​of that "name"
        branch_name = request.POST.getlist("branch_name[]")
        branch_addresses  = request.POST.getlist("branch_address[]")

        # --- 1. Preliminary validations ---
        errors = []

        if not name:
            errors.append("El nombre es obligatorio.")
        if not phone:
            errors.append("El teléfono es obligatorio.")
        if name and Company.objects.filter(name=name).exists():
            errors.append("El nombre de la compañía ya existe.")

        # Verify that there is at least one branch with data
        valid_branches = [
            (n.strip(), a.strip())
            for n, a in zip(branch_name, branch_addresses)
            if n.strip() or a.strip()
        ]

        if not valid_branches:
            errors.append("Debes agregar al menos una sucursal.")
        else:
            for n, a in valid_branches:
                if not n:
                    errors.append("Todas las sucursales deben tener un nombre.")
                    break
                if not a:
                    errors.append("Todas las sucursales deben tener una dirección.")
                    break

        if errors:
            messages.error(request, errors[0])

            # The form is re-rendered with the existing text and the company queryset intact.
            return render(request, 'companies/create_companies.html', {
                'name': name,
                'branch_name': branch_name,
                'phone': phone,
                'address': branch_addresses,
                'is_active': is_active
            })

        # --- 2. Creation within a transaction ---
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

        return redirect('companies_list') # Post/Redirect/Get: avoids duplicate forwarding    
    return render(request, 'companies/create_companies.html')

# Update companies/branch
@login_required
@superuser_required
def update_companies(request, companies_id):
    company = get_object_or_404(Company, id=companies_id)
    branches = Branch.objects.filter(company=company)

    context = {'company': company, 'branches': branches}

    if request.method == 'POST':
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()

        branch_ids = request.POST.getlist("branch_id[]")
        branch_names = request.POST.getlist("branch_name[]")
        branch_addresses = request.POST.getlist("branch_address[]")

        # --- 1. Preliminary validations ---
        errors = []

        if not name:
            errors.append("El nombre es obligatorio.")
        if not phone:
            errors.append("El teléfono es obligatorio.")

        # At least one branch with complete data
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

        # --- 2. Update within a transaction ---
        try:
            with transaction.atomic():
                company.name = name
                company.phone_number = phone
                company.save()

                for b_id, b_name, b_address in zip(branch_ids, branch_names, branch_addresses):
                    b_name = b_name.strip()
                    b_address = b_address.strip()

                    if not b_name and not b_address:
                        continue # Empty row, ignored

                    if b_id:
                        Branch.objects.filter(id=b_id, company=company).update(
                            name=b_name,
                            address=b_address,
                        )
                    else:
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

# Active Branch
@login_required
@superuser_required
def active_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_active = True
    branch.save()
    return redirect('company:update', companies_id=branch.company_id)

# Inactive Branch
@login_required
@superuser_required
def inactive_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_active = False
    branch.save()
    return redirect('company:update', companies_id=branch.company_id)