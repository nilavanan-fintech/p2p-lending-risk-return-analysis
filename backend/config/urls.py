from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Liveness probe used by Docker health checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/analytics/", include("reporting.urls")),
]
