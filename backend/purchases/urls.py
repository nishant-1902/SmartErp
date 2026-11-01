"""URL routes for purchase-order operations."""

from django.urls import path

from purchases import views

app_name = "purchases"

urlpatterns = [
    path("", views.purchase_orders_list_create_view, name="list-create"),
    path(
        "<str:purchase_order_id>/submit/",
        views.purchase_order_submit_view,
        name="submit",
    ),
    path(
        "<str:purchase_order_id>/approve/",
        views.purchase_order_approve_view,
        name="approve",
    ),
    path(
        "<str:purchase_order_id>/reject/",
        views.purchase_order_reject_view,
        name="reject",
    ),
    path(
        "<str:purchase_order_id>/cancel/",
        views.purchase_order_cancel_view,
        name="cancel",
    ),
    path(
        "<str:purchase_order_id>/receive/",
        views.purchase_order_receive_view,
        name="receive",
    ),
    path(
        "<str:purchase_order_id>/",
        views.purchase_order_detail_view,
        name="detail",
    ),
]
