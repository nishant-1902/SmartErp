"""Fixed report routes; keep specific report names explicit."""

from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("sales/", views.sales_view, name="sales"),
    path("inventory/", views.inventory_view, name="inventory"),
    path("low-stock/", views.low_stock_view, name="low-stock"),
    path("employees/", views.employees_view, name="employees"),
    path("departments/", views.departments_view, name="departments"),
    path("suppliers/", views.suppliers_view, name="suppliers"),
    path("purchases/", views.purchases_view, name="purchases"),
    path("monthly-sales/", views.monthly_sales_view, name="monthly-sales"),
]
