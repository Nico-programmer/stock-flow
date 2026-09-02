from django.urls import path
from .views import *

app_name = "inventory"

urlpatterns = [
    path("", inventory_list, name="inventory_list"),

    # Producto
    path("products/", product_list, name="product_list"),
    path("create-product/", create_product, name="create_product"),
    path("update-product/<int:product_id>/", update_product, name="update_product"),
    path("active-product/<int:product_id>/", active_product, name="active_product"),
    path("inactive-product/<int:product_id>/", inactive_product, name="inactive_product"),
]
