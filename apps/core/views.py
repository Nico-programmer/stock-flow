from django.shortcuts import render
from django.contrib.auth.decorators import login_required

""" Dashboard View """
@login_required
def dashboard(request):
    return render(request, 'layout.html')