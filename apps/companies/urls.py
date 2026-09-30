from django.urls import path

# Vistas
from .views import *

# We define the namespace of the URLs
app_name = 'company'

urlpatterns = [
    path('', companies_list, name="list"),
    path('info/', company_info, name="info"),
    path('info/<int:company_id>/', company_info, name="info"),
    path('create-companies/', create_companies, name="create"),
    path('update-companies/<int:companies_id>/', update_companies, name="update"),

    # Branch CRUD (Gerente General de su propia empresa, o admin de plataforma con company_id)
    path('create-branch/', create_branch, name="branch_create"),
    path('create-branch/<int:company_id>/', create_branch, name="branch_create"),
    path('update-branch/<int:branch_id>/', update_branch, name="branch_update"),
    path('branch-active/<int:branch_id>/', active_branch, name="active_branch"),
    path('branch-inactive/<int:branch_id>/', inactive_branch, name="inactive_branch"),
    path('branch-deactivate-review/<int:branch_id>/', branch_deactivate_review, name="branch_deactivate_review"),
    path('branch-deactivate-process/<int:branch_id>/', branch_deactivate_process, name="branch_deactivate_process"),

    # Endpoint
    path('get-branches/<int:company_id>/', get_branches_by_company, name='get_branches_by_company'),
]
