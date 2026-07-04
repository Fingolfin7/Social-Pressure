import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Activity, EventLog, MemberTarget, Membership, Project, PushSubscription
from .progress import home_summary, project_member_progress
from .push import send_push_to_user
from .utils import get_period_bounds


NUMBER_WORDS = {
    0: "Zero",
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
}

CADENCE_LABELS = {
    Activity.Cadence.DAILY: "daily",
    Activity.Cadence.WEEKLY: "weekly",
    Activity.Cadence.MONTHLY: "monthly",
}

CADENCE_NOUNS = {
    Activity.Cadence.DAILY: "day",
    Activity.Cadence.WEEKLY: "week",
    Activity.Cadence.MONTHLY: "month",
}

CADENCE_DONE_COPY = {
    Activity.Cadence.DAILY: "today",
    Activity.Cadence.WEEKLY: "this week",
    Activity.Cadence.MONTHLY: "this month",
}


@login_required
@ensure_csrf_cookie
def home(request):
    projects = (
        Project.objects.filter(members=request.user)
        .prefetch_related("activities", "memberships__user")
        .order_by("created_at")
    )
    project_cards = [_project_card(project, request.user) for project in projects]
    project_cards.sort(key=lambda card: (not card["current_user_behind"], -card["recent_ts"]))
    partner_count = home_summary(request.user)
    return render(
        request,
        "core/home.html",
        {
            "greeting": _greeting_word(),
            "display_name": request.user.first_name or request.user.username,
            "summary_line": _summary_line(partner_count),
            "project_cards": project_cards,
            "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        },
    )


@login_required
def project_create(request):
    values = _project_create_values(request.POST if request.method == "POST" else None)
    errors = {}

    if request.method == "POST":
        errors = _validate_project_create(values)
        if not errors:
            with transaction.atomic():
                project = Project.objects.create(
                    name=values["name"],
                    created_by=request.user,
                    end_date=values["end_date_obj"] if values["duration"] == "until" else None,
                )
                Activity.objects.create(
                    project=project,
                    name=values["activity"],
                    unit=values["unit"],
                    cadence=values["cadence"],
                )
                Membership.objects.create(project=project, user=request.user)
            return redirect("project_target", pk=project.pk)

    return render(
        request,
        "core/project_create.html",
        {
            "values": values,
            "errors": errors,
            "cadences": Activity.Cadence.choices,
            "recap": _create_recap(values),
        },
    )


@login_required
def project_target(request, pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    membership = get_object_or_404(Membership, project=project, user=request.user)
    target = MemberTarget.objects.filter(membership=membership, activity=activity).first()
    value = target.target if target else 3
    error = ""

    if request.method == "POST":
        value = _clamp_target(request.POST.get("target"))
        MemberTarget.objects.update_or_create(
            membership=membership,
            activity=activity,
            defaults={"target": value},
        )
        return redirect("project_detail", pk=project.pk)

    return render(
        request,
        "core/project_target.html",
        {
            "project": project,
            "activity": activity,
            "value": value,
            "error": error,
            "unit_plural": _plural_unit(activity.unit),
            "cadence_noun": CADENCE_NOUNS.get(activity.cadence, activity.cadence),
        },
    )


@login_required
def project_detail(request, pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    progress = _renderable_progress(project_member_progress(project, request.user))
    missing_target = not MemberTarget.objects.filter(
        membership__project=project,
        membership__user=request.user,
        activity=activity,
    ).exists()
    return render(
        request,
        "core/project_detail.html",
        {
            "project": project,
            "activity": activity,
            "progress": progress,
            "missing_target": missing_target,
            "unit_plural": _plural_unit(activity.unit),
            "cadence_noun": CADENCE_NOUNS.get(activity.cadence, activity.cadence),
        },
    )


def offline(request):
    return render(request, "core/offline.html")


def _member_project_or_404(pk, user):
    return get_object_or_404(
        Project.objects.prefetch_related("activities", "memberships__user"),
        pk=pk,
        memberships__user=user,
    )


def _first_activity_or_404(project):
    activity = project.activities.order_by("created_at", "pk").first()
    if not activity:
        raise Http404("Project has no activity.")
    return activity


def _greeting_word():
    hour = timezone.localtime().hour
    if hour < 12:
        return "Morning"
    if hour < 18:
        return "Afternoon"
    return "Evening"


def _summary_line(partner_count):
    if partner_count == 0:
        return "All caught up. Nice."
    word = NUMBER_WORDS.get(partner_count, str(partner_count))
    if partner_count == 1:
        return f"{word} person is counting on you this week."
    return f"{word} people are counting on you this week."


def _project_create_values(data=None):
    values = {
        "template": "gym",
        "name": "Gym Buddies",
        "activity": "Sessions",
        "unit": "session",
        "cadence": Activity.Cadence.WEEKLY,
        "duration": "open",
        "end_date": "",
        "end_date_obj": None,
    }
    if data is None:
        return values

    values.update(
        {
            "template": data.get("template", "custom"),
            "name": data.get("name", "").strip(),
            "activity": data.get("activity", "").strip(),
            "unit": data.get("unit", "").strip(),
            "cadence": data.get("cadence", Activity.Cadence.WEEKLY),
            "duration": data.get("duration", "open"),
            "end_date": data.get("end_date", "").strip(),
            "end_date_obj": None,
        }
    )
    return values


def _validate_project_create(values):
    errors = {}
    if not values["name"]:
        errors["name"] = "Name this project."
    elif len(values["name"]) > Project._meta.get_field("name").max_length:
        errors["name"] = "That name's too long - 100 characters max."

    if not values["activity"]:
        errors["activity"] = "Name what you'll count."
    elif len(values["activity"]) > Activity._meta.get_field("name").max_length:
        errors["activity"] = "That activity's too long - 100 characters max."

    if not values["unit"]:
        errors["unit"] = "Name one count."
    elif len(values["unit"]) > Activity._meta.get_field("unit").max_length:
        errors["unit"] = "That unit's too long - 50 characters max."

    if values["cadence"] not in Activity.Cadence.values:
        errors["cadence"] = "Choose how often."

    if values["duration"] == "until":
        if not values["end_date"]:
            errors["end_date"] = "Choose the date you'll keep going until."
        else:
            try:
                end_date = datetime.strptime(values["end_date"], "%Y-%m-%d").date()
            except ValueError:
                errors["end_date"] = "Use a real date."
            else:
                if end_date <= timezone.localdate():
                    errors["end_date"] = "Choose a future date."
                else:
                    values["end_date_obj"] = end_date
    else:
        values["duration"] = "open"

    return errors


def _create_recap(values):
    cadence = CADENCE_NOUNS.get(values.get("cadence"), "week")
    unit = values.get("unit") or "sessions"
    activity = values.get("activity") or "sessions"
    return {
        "unit": _plural_unit(unit),
        "activity": activity.lower(),
        "cadence": cadence,
    }


def _clamp_target(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 3
    return min(99, max(1, number))


def _plural_unit(unit):
    unit = unit.strip() if unit else "session"
    if unit.endswith("s"):
        return unit
    return f"{unit}s"


def _project_card(project, user):
    activity = project.activities.order_by("created_at", "pk").first()
    progress = _renderable_progress(project_member_progress(project, user))
    current = next((item for item in progress if item["is_current_user"]), None)
    partner_names = [
        item["user"].first_name or item["user"].username
        for item in progress
        if not item["is_current_user"]
    ]
    recent = (
        EventLog.objects.filter(activity__project=project)
        .order_by("-logged_at")
        .values_list("logged_at", flat=True)
        .first()
    )
    recent_ts = recent.timestamp() if recent else project.created_at.timestamp()

    status = _project_status(activity, progress, current)
    with_line = f"with {', '.join(partner_names)}" if partner_names else "just you"
    return {
        "project": project,
        "activity": activity,
        "activity_name": activity.name if activity else "No activity yet",
        "cadence": CADENCE_LABELS.get(activity.cadence, activity.cadence) if activity else "weekly",
        "with_line": with_line,
        "status": status,
        "progress": progress,
        "current_user_behind": bool(current and current["behind"]),
        "recent_ts": recent_ts,
    }


def _project_status(activity, progress, current):
    if current and current["behind"]:
        behind_by = current["target_count"] - current["count"]
        return {
            "class": "pill--behind",
            "text": f"You're {behind_by} behind",
        }

    with_targets = [item for item in progress if item["target"]]
    if with_targets and len(with_targets) == len(progress) and all(item["met"] for item in with_targets):
        done_copy = CADENCE_DONE_COPY.get(activity.cadence, "this week") if activity else "this week"
        return {
            "class": "pill--done",
            "text": f"All set {done_copy}",
        }

    days_left = _days_left(activity.cadence if activity else Activity.Cadence.WEEKLY)
    return {
        "class": "pill--period",
        "text": "Today" if days_left <= 1 else f"{days_left} days left",
    }


def _days_left(cadence):
    _start, end = get_period_bounds(cadence)
    seconds = max(0, (end - timezone.now()).total_seconds())
    days = int((seconds + 86399) // 86400)
    return max(1, days)


def _renderable_progress(progress):
    rendered = []
    for item in progress:
        next_item = dict(item)
        target_count = item["target_count"]
        if target_count:
            dot_count = min(target_count, 10)
            filled = min(item["count"], dot_count)
            next_item["dots"] = [
                {"filled": index < filled}
                for index in range(dot_count)
            ]
            next_item["overflow"] = max(0, item["count"] - target_count)
        else:
            next_item["dots"] = []
            next_item["overflow"] = 0
        rendered.append(next_item)
    return rendered


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
