from django.shortcuts import render

# Import models
from .models import *

# Import decorators
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import superuser_required

# Import paginator's
from django.core.paginator import Paginator
from django.db.models import Q

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