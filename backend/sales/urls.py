"""URL routes for sales-order management."""

from django.urls import path

from sales import views

app_name = "sales"

urlpatterns = [
    path("", views.sales_orders_list_create_view, name="list-create"),
    path(
        "<str:sales_order_id>/confirm/",
        views.sales_order_confirm_view,
        name="confirm",
    ),
    path(
        "<str:sales_order_id>/cancel/",
        views.sales_order_cancel_view,
        name="cancel",
    ),
    path(
        "<str:sales_order_id>/fulfill/",
        views.sales_order_fulfill_view,
        name="fulfill",
    ),
    path(
        "<str:sales_order_id>/payments/",
        views.sales_order_payment_view,
        name="payment",
    ),
    path(
        "<str:sales_order_id>/returns/",
        views.sales_order_return_view,
        name="return",
    ),
    path("<str:sales_order_id>/", views.sales_order_detail_view, name="detail"),
]
