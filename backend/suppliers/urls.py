"""URL routes for supplier endpoints."""

from django.urls import path

from suppliers import views

app_name = "suppliers"

urlpatterns = [
    path("", views.suppliers_list_create_view, name="list-create"),
    path(
        "<str:supplier_id>/purchase-orders/",
        views.supplier_purchase_orders_view,
        name="purchase-orders",
    ),
    path("<str:supplier_id>/", views.supplier_detail_view, name="detail"),
]
