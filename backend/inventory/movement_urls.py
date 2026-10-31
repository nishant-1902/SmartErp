"""URL routes for stock movement history."""

from django.urls import path

from inventory import views

app_name = "stock_movements"

urlpatterns = [
    path("", views.stock_movements_view, name="list"),
]
