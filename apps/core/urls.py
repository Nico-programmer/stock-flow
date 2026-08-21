from django.urls import path

# Import Views
from .views import *

urlpatterns = [
    path('', dashboard, name="dashboard"),
]
