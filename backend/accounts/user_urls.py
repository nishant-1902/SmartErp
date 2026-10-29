"""User-management and audit-log URL routes."""

from django.urls import path

from accounts import views

app_name = "user-management"

urlpatterns = [
    path("", views.users_list_create_view, name="user-list-create"),
    path(
        "<str:user_id>/activate/",
        views.user_activate_view,
        name="user-activate",
    ),
    path(
        "<str:user_id>/deactivate/",
        views.user_deactivate_view,
        name="user-deactivate",
    ),
    path(
        "<str:user_id>/reset-password/",
        views.user_reset_password_view,
        name="user-reset-password",
    ),
    path("<str:user_id>/", views.user_detail_view, name="user-detail"),
]
