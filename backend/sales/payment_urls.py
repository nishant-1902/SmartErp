"""URL routes for payment history."""

from django.urls import path

from sales.views import payments_list_view

app_name = "payments"

urlpatterns = [
    path("", payments_list_view, name="list"),
]
