from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import *

@login_required
def inventory_list(request):
    return render(request, "inventory_list.html")