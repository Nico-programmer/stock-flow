from django.urls import path

# Import views
from django.contrib.auth.views import LogoutView
from .views import *

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]
