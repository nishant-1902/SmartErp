"""URL routes for customer records and sales-order history."""

from django.urls import path

from customers import views

app_name = "customers"

urlpatterns = [
    path("", views.customers_list_create_view, name="list-create"),
    path(
        "<str:customer_id>/sales-orders/",
        views.customer_sales_orders_view,
        name="sales-orders",
    ),
    path("<str:customer_id>/", views.customer_detail_view, name="detail"),
]
