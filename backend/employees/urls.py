"""URL routes for employee endpoints."""

from django.urls import path

from employees import views

app_name = "employees"

urlpatterns = [
    path("", views.employees_list_create_view, name="list-create"),
    path("me/", views.employee_me_view, name="me"),
    path("designations/", views.employee_designations_view, name="designations"),
    path("<str:employee_id>/", views.employee_detail_view, name="detail"),
]
