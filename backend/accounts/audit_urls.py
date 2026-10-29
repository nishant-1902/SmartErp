"""Audit-log URL routes."""

from django.urls import path

from accounts.views import audit_logs_list_view

app_name = "audit-logs"

urlpatterns = [
    path("", audit_logs_list_view, name="audit-log-list"),
]
