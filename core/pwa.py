from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404, JsonResponse
from django.templatetags.static import static
from django.views.decorators.cache import never_cache


THEME_COLOR = "#f7f1e7"
BACKGROUND_COLOR = "#f7f1e7"


def manifest(request):
    return JsonResponse(
        {
            "name": "Social Pressure",
            "short_name": "Pressure",
            "description": "Accountability partners for your goals.",
            "id": "/",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": BACKGROUND_COLOR,
            "theme_color": THEME_COLOR,
            "icons": [
                {
                    "src": static("core/images/icons/social-pressure-icon-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("core/images/icons/social-pressure-icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("core/images/icons/social-pressure-maskable-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


@never_cache
def service_worker(request):
    service_worker_path = finders.find("core/pwa/service-worker.js")
    if not service_worker_path:
        raise Http404("Service worker not found")

    response = FileResponse(
        open(service_worker_path, "rb"),
        content_type="text/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    return response
