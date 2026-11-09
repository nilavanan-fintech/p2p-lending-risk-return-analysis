from django.urls import path

from . import views

urlpatterns = [
    path("sources/", views.sources),
    path("status-summary/", views.status_summary),
    path("default-rate/<str:dimension>/", views.default_rate),
    path("vintage/", views.vintage),
    path("returns/<str:dimension>/", views.returns),
    path("portfolio/<str:dimension>/", views.portfolio),
    path("concentration/<str:dimension>/", views.concentration),
    path("default-exposure/", views.default_exposure),
    path("india-rules/", views.india_rules),
    path("loans.csv", views.loans_export),
]
