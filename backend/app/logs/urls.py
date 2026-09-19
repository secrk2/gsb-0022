from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("meta", views.MetaView.as_view(), name="meta"),
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),
    path("logs/search", views.LogSearchView.as_view(), name="log-search"),
]
