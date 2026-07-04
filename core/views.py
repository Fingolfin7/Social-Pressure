import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Project, PushSubscription
from .push import send_push_to_user


@login_required
@ensure_csrf_cookie
def home(request):
    projects = (
        Project.objects.filter(members=request.user)
        .prefetch_related("activities")
        .order_by("name")
    )
    return render(
        request,
        "core/home.html",
        {
            "projects": projects,
            "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        },
    )


def offline(request):
    return render(request, "core/offline.html")


def json_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def get_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


@login_required
@require_POST
def push_subscribe(request):
    data = get_json_body(request)
    if data is None:
        return json_error("Invalid JSON.")

    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not endpoint or not p256dh or not auth:
        return json_error("Subscription endpoint and keys are required.")

    PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
        },
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    data = get_json_body(request)
    if data is None:
        return json_error("Invalid JSON.")

    endpoint = data.get("endpoint")
    if not endpoint:
        return json_error("Subscription endpoint is required.")

    PushSubscription.objects.filter(
        user=request.user,
        endpoint=endpoint,
    ).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_test(request):
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        return json_error("VAPID keys are not configured.")

    if not request.user.push_subscriptions.exists():
        return json_error("No push subscriptions found for this user.")

    sent = send_push_to_user(
        request.user,
        {
            "title": "Social Pressure",
            "body": "Push works! \U0001f389",
            "url": "/",
        },
    )
    return JsonResponse({"sent": sent})
