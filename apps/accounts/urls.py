from django.urls import path

# Import views
from django.contrib.auth.views import LogoutView
from .views import *

# We define the namespace of the URLs
app_name = "account"

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Users Wiews
    path('user-list/', userList_view, name="list"),
    path('create-user/', create_user, name="create"),
    path('update-user/<int:user_id>/', update_user, name="update"),
    path('desactive-user/<int:user_id>/', deactivate_user, name="deactivate"),
    path('activate-user/<int:user_id>/', activate_user, name="activate"),

    # Groups Views
    path('group-list/', group_list, name="group_list"),
    path('assign-template/', assign_template, name="group_assign"),
    path('edit-company-templates/<int:company_id>/', edit_company_templates, name="group_edit"),
    path('delete-group/<int:group_id>/', delete_group, name="group_delete"),

    # Group Templates Views
    path('template-list/', template_list, name="template_list"),
    path('create-template/', create_template, name="template_create"),
    path('update-template/<int:template_id>/', update_template, name="template_update"),
    path('delete-template/<int:template_id>/', delete_template, name="template_delete"),

    # Endpoint
    path('get-groups/<int:company_id>/', get_groups_by_company, name='get_groups_by_company'),
    path('get-branches/<int:company_id>/', get_branches_by_company, name='get_branches_by_company'),
]
