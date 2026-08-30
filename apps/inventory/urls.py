from django.urls import path
from .views import *

app_name = "inventory"

urlpatterns = [
    path("", inventory_list, name="inventory_list"),
]
