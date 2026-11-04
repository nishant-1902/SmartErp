"""URL routes for invoice access."""

from django.urls import path

from sales.views import invoice_detail_view, invoices_list_view

app_name = "invoices"

urlpatterns = [
    path("", invoices_list_view, name="list"),
    path("<str:invoice_id>/", invoice_detail_view, name="detail"),
]
