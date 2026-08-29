from django.urls import path

# Vistas
from .views import *

# We define the namespace of the URLs
app_name = 'company'

urlpatterns = [
    path('', companies_list, name="list"),
    path('create-companies/', create_companies, name="create"),
    path('update-companies/<int:companies_id>/', update_companies, name="update"),

    # Active/Inactive Branch
    path('branch-active/<int:branch_id>/', active_branch, name="active_branch"),
    path('branch-inactive/<int:branch_id>/', inactive_branch, name="inactive_branch"),

    # Endpoint
    path('get-branches/<int:company_id>/', get_branches_by_company, name='get_branches_by_company'),
]
