"""URL routes for product catalogue endpoints."""

from django.urls import path

from inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.products_list_create_view, name="list-create"),
    path("low-stock/", views.low_stock_products_view, name="low-stock"),
    path("categories/", views.product_categories_view, name="categories"),
    path("<str:product_id>/", views.product_detail_view, name="detail"),
]
