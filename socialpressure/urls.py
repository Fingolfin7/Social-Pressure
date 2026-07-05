from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import pwa
from core.views import (
    home,
    offline,
    project_create,
    project_detail,
    project_join,
    project_target,
    push_subscribe,
    push_test,
    push_unsubscribe,
)

urlpatterns = [
    path("", home, name="home"),
    path("manifest.json", pwa.manifest, name="manifest"),
    path("service-worker.js", pwa.service_worker, name="service_worker"),
    path("offline/", offline, name="offline"),
    path("join/<uuid:token>/", project_join, name="project_join"),
    path("projects/new/", project_create, name="project_create"),
    path("projects/<int:pk>/", project_detail, name="project_detail"),
    path("projects/<int:pk>/target/", project_target, name="project_target"),
    path("push/subscribe/", push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", push_unsubscribe, name="push_unsubscribe"),
    path("push/test/", push_test, name="push_test"),
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
