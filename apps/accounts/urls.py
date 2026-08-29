from django.urls import path

# Import views
from django.contrib.auth.views import LogoutView
from .views import *

# We define the namespace of the URLs
app_name = "account"

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # Users Wiews
    path('user-list/', userList_view, name="list"),
    path('create-user/', create_user, name="create"),
    path('update-user/<int:user_id>/', update_user, name="update"),
    path('desactive-user/<int:user_id>/', deactivate_user, name="deactivate"),
    path('activate-user/<int:user_id>/', activate_user, name="activate"),
]
