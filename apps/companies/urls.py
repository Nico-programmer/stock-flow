from django.urls import path

# Vistas
from .views import *

urlpatterns = [
    path('', companies_list, name="companies_list"),
    path('create-companies/', create_companies, name="create_companies"),
    path('update-companies/<int:companies_id>/', update_companies, name="update_companies"),
]
