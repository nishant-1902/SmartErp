"""URL routes for stock adjustment and immutable movement history."""

from django.urls import path

from inventory import views

app_name = "stock"

urlpatterns = [
    path("", views.stock_adjustments_view, name="adjustments"),
]

