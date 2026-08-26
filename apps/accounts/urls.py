from django.urls import path

# Import views
from django.contrib.auth.views import LogoutView
from .views import *

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # Users Wiews
    path('user-list/', userList_view, name="users_list"),
    path('create-user/', create_user, name="users_create"),
    path('update-user/<int:user_id>/', update_user, name="update_user"),
    path('desactive-user/<int:user_id>/', deactivate_user, name="deactivate_user"),
    path('activate-user/<int:user_id>/', activate_user, name="activate_user"),
]
