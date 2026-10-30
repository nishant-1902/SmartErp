"""URL routes for department endpoints."""

from django.urls import path

from departments import views

app_name = "departments"

urlpatterns = [
    path("", views.departments_list_create_view, name="list-create"),
    path(
        "<str:department_id>/employees/",
        views.department_employees_view,
        name="employees",
    ),
    path("<str:department_id>/", views.department_detail_view, name="detail"),
]
