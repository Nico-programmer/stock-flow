from django.urls import path

# Import views
from .views import *

# We define the namespace of the URLs
app_name = "inventory"

urlpatterns = [
    # Category Views
    path('category-list/', category_list, name="category_list"),
    path('create-category/', create_category, name="category_create"),
    path('update-category/<int:category_id>/', update_category, name="category_update"),
    path('delete-category/<int:category_id>/', delete_category, name="category_delete"),

    # Product Views (sin company_id: usuario de negocio ve la suya / con company_id: soporte del admin)
    path('product-list/', product_list, name="product_list"),
    path('product-list/<int:company_id>/', product_list, name="product_list"),
    path('create-product/', create_product, name="product_create"),
    path('create-product/<int:company_id>/', create_product, name="product_create"),
    path('product-detail/<int:product_id>/', product_detail, name="product_detail"),
    path('update-product/<int:product_id>/', update_product, name="product_update"),
    path('deactivate-product/<int:product_id>/', deactivate_product, name="product_deactivate"),
    path('activate-product/<int:product_id>/', activate_product, name="product_activate"),
]
