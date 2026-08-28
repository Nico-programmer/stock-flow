from django.urls import path

# Vistas
from .views import *

urlpatterns = [
    path('', companies_list, name="companies_list"),
]
