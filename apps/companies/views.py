from django.shortcuts import render

# Decorators
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import superuser_required

@login_required
@superuser_required
def companies_list(request):
    return render(request, "companies.html")