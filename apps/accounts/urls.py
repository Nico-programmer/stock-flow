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
    path('create-group/', create_group, name="group_create"),
    path('update-group/<int:group_id>/', update_group, name="group_update"),
    path('delete-group/<int:group_id>/', delete_group, name="group_delete"),

    # Endpoint
    path('get-groups/<int:company_id>/', get_groups_by_company, name='get_groups_by_company'),
]
