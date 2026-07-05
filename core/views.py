import json
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Activity, EventLog, MemberTarget, Membership, Nudge, Project, PushSubscription
from .progress import home_summary, member_streak, period_counts, project_member_progress
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
def project_join(request, token):
    project = get_object_or_404(
        Project.objects.prefetch_related("activities", "memberships__user"),
        invite_token=token,
    )
    activity = _first_activity_or_404(project)
    if Membership.objects.filter(project=project, user=request.user).exists():
        return redirect("project_detail", pk=project.pk)

    inviter = project.created_by
    inviter_name = _inviter_display_name(project)
    default_target = _inviter_target(project, activity, inviter) or 3
    value = default_target

    if request.method == "POST":
        value = _clamp_target(request.POST.get("target"))
        with transaction.atomic():
            membership, _created = Membership.objects.get_or_create(
                project=project,
                user=request.user,
            )
            MemberTarget.objects.update_or_create(
                membership=membership,
                activity=activity,
                defaults={"target": value},
            )
        return redirect("project_detail", pk=project.pk)

    return render(
        request,
        "core/project_join.html",
        {
            "project": project,
            "activity": activity,
            "inviter": inviter,
            "inviter_name": inviter_name,
            "value": value,
            "detail_rows": _join_detail_rows(project, activity),
            "unit_plural": _plural_unit(activity.unit),
            "cadence_label": CADENCE_LABELS.get(activity.cadence, activity.cadence),
            "cadence_noun": CADENCE_NOUNS.get(activity.cadence, activity.cadence),
        },
    )


@login_required
def project_detail(request, pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    raw_progress = project_member_progress(project, request.user)
    progress = _renderable_progress(_progress_with_display(raw_progress, activity))
    period_start, period_end = get_period_bounds(activity.cadence)
    show_earlier = request.GET.get("earlier") == "1"
    feed = _project_feed(
        project,
        activity,
        request.user,
        raw_progress,
        period_start,
        period_end,
        show_earlier,
    )
    missing_target = not MemberTarget.objects.filter(
        membership__project=project,
        membership__user=request.user,
        activity=activity,
    ).exists()
    join_path = reverse("project_join", kwargs={"token": project.invite_token})
    return render(
        request,
        "core/project_detail.html",
        {
            "project": project,
            "activity": activity,
            "progress": progress,
            "project_description": _project_description(project, activity),
            "period_chip": _period_chip(activity, period_start, period_end),
            "feed_title": _feed_title(activity.cadence),
            "feed_checkin_count": feed["checkin_count"],
            "feed_checkin_label": _checkin_label(feed["checkin_count"]),
            "feed_sections": feed["sections"],
            "feed_empty": feed["empty"],
            "show_earlier_link": feed["show_earlier_link"],
            "missing_target": missing_target,
            "solo_project": len(progress) == 1,
            "invite_url": request.build_absolute_uri(join_path),
            "unit_plural": _plural_unit(activity.unit),
            "cadence_noun": CADENCE_NOUNS.get(activity.cadence, activity.cadence),
        },
    )


@login_required
def event_log(request, pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    membership = get_object_or_404(Membership, project=project, user=request.user)
    target = MemberTarget.objects.filter(membership=membership, activity=activity).first()
    period_start, period_end = get_period_bounds(activity.cadence)
    current_count = period_counts(activity, period_start, period_end).get(request.user.id, 0)
    new_count = current_count + 1
    partners = list(
        project.memberships.exclude(user=request.user)
        .select_related("user")
        .order_by("joined_at", "pk")
    )

    if request.method == "POST":
        logged_at = timezone.now()
        event = EventLog.objects.create(
            activity=activity,
            user=request.user,
            logged_at=logged_at,
            note=request.POST.get("note", "")[:280].strip(),
        )
        period_start, period_end = get_period_bounds(activity.cadence, logged_at)
        new_count = period_counts(activity, period_start, period_end).get(request.user.id, 0)
        partner_users = [partner.user for partner in partners]
        partners_with_subscriptions = (
            PushSubscription.objects.filter(user__in=partner_users)
            .values("user_id")
            .distinct()
            .count()
        )
        sent = 0
        try:
            detail_url = request.build_absolute_uri(
                reverse("project_detail", kwargs={"pk": project.pk})
            )
            logger_name = request.user.first_name or request.user.username
            cadence_noun = CADENCE_NOUNS.get(activity.cadence, activity.cadence)
            count_copy = str(new_count)
            if target:
                count_copy = f"{new_count}/{target.target}"
            body = (
                f"{logger_name} logged a {activity.unit} "
                f"({count_copy} this {cadence_noun})"
            )
            payload = {"title": project.name, "body": body, "url": detail_url}
            for partner in partner_users:
                sent += send_push_to_user(partner, payload)
        except Exception:
            pass

        logged_url = reverse(
            "event_logged",
            kwargs={"pk": project.pk, "event_pk": event.pk},
        )
        return redirect(f"{logged_url}?partners={partners_with_subscriptions}")

    return render(
        request,
        "core/event_log.html",
        {
            "project": project,
            "activity": activity,
            "support": _log_support_copy(partners, target, new_count, activity.cadence),
            "current_initial": (request.user.first_name or request.user.username)[:1],
        },
    )


@login_required
def event_logged(request, pk, event_pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    event = get_object_or_404(
        EventLog.objects.select_related("activity", "user"),
        pk=event_pk,
        user=request.user,
        activity=activity,
    )
    membership = get_object_or_404(Membership, project=project, user=request.user)
    target = MemberTarget.objects.filter(membership=membership, activity=activity).first()
    period_start, period_end = get_period_bounds(activity.cadence, event.logged_at)
    count = period_counts(activity, period_start, period_end).get(request.user.id, 0)
    streak = member_streak(membership, activity, event.logged_at)
    partner_count = _positive_int(request.GET.get("partners"))
    receipt = _push_receipt(project, request.user, partner_count)

    return render(
        request,
        "core/event_logged.html",
        {
            "project": project,
            "activity": activity,
            "event": event,
            "body": _logged_body(target, count, activity.cadence, streak),
            "receipt": receipt,
        },
    )


@login_required
@require_POST
def event_undo(request, pk, event_pk):
    project = _member_project_or_404(pk, request.user)
    activity = _first_activity_or_404(project)
    event = EventLog.objects.filter(pk=event_pk, activity=activity).first()

    if event and event.user_id == request.user.id:
        if event.created_at >= timezone.now() - timedelta(minutes=2):
            event.delete()
        else:
            messages.info(request, "Too late to undo that one.")

    return redirect("project_detail", pk=project.pk)


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


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _partner_phrase(partners):
    if not partners:
        return ""
    if len(partners) == 1:
        user = partners[0].user
        return user.first_name or user.username
    return "your partners"


def _log_support_copy(partners, target, new_count, cadence):
    cadence_noun = CADENCE_NOUNS.get(cadence, cadence)
    if len(partners) == 1:
        opening = f"Tap once and {_partner_phrase(partners)} finds out right away."
    elif partners:
        opening = "Tap once and your partners find out right away."
    else:
        opening = "Tap once and it's on the record."

    if not target:
        return {
            "opening": opening,
            "count": str(new_count),
            "suffix": f" this {cadence_noun}.",
        }

    count = f"{new_count} of {target.target}"
    if new_count >= target.target:
        suffix = f" — your whole {cadence_noun}, done."
    else:
        remaining = target.target - new_count
        remaining_copy = "one more" if remaining == 1 else f"{remaining} more"
        suffix = f" — {remaining_copy} after this."
    return {"opening": opening, "count": count, "suffix": suffix}


def _logged_body(target, count, cadence, streak):
    period_copy = f"this {CADENCE_NOUNS.get(cadence, cadence)}"
    if not target:
        return {
            "count": str(count),
            "suffix": f" {period_copy}.",
            "streak": "",
        }

    count_copy = f"{count} of {target.target}"
    if count >= target.target:
        suffix = f" {period_copy} — you hit it."
        if streak >= 1:
            suffix += " Your streak just ticked up to "
        return {
            "count": count_copy,
            "suffix": suffix,
            "streak": _streak_count_copy(cadence, streak) if streak >= 1 else "",
        }

    remaining = target.target - count
    remaining_copy = "one" if remaining == 1 else str(remaining)
    return {
        "count": count_copy,
        "suffix": f" {period_copy} — {remaining_copy} to go.",
        "streak": "",
    }


def _streak_count_copy(cadence, streak):
    if cadence == Activity.Cadence.DAILY:
        return f"Day {streak}"
    noun = CADENCE_NOUNS.get(cadence, "week")
    if streak != 1:
        noun = f"{noun}s"
    return f"{streak} {noun}"


def _push_receipt(project, current_user, partner_count):
    if partner_count < 1:
        return None

    partners = list(
        project.memberships.exclude(user=current_user)
        .filter(user__push_subscriptions__isnull=False)
        .select_related("user")
        .distinct()
        .order_by("joined_at", "pk")
    )
    if partner_count == 1 and partners:
        name = partners[0].user.first_name or partners[0].user.username
        return {"initial": name[:1], "text": f"{name} just got the notification"}
    return {"initial": "Y", "text": "Your partners just got the notification"}


def _project_description(project, activity):
    if project.description:
        return project.description
    cadence = CADENCE_NOUNS.get(activity.cadence, "week")
    unit = activity.unit or "session"
    return f"One {unit} at a time, every {cadence}."


def _display_name(user, is_current_user=False):
    if is_current_user:
        return "You"
    return user.first_name or user.username


def _inviter_display_name(project):
    if project.created_by:
        return project.created_by.first_name or project.created_by.username
    return "Your partner"


def _inviter_target(project, activity, inviter):
    if not inviter:
        return None
    target = MemberTarget.objects.filter(
        membership__project=project,
        membership__user=inviter,
        activity=activity,
    ).first()
    return target.target if target else None


def _join_detail_rows(project, activity):
    rows = [
        {"key": "Project", "value": project.name},
        {
            "key": "You'll count",
            "value": f"{activity.name}, {CADENCE_LABELS.get(activity.cadence, activity.cadence)}",
        },
    ]
    cadence_noun = CADENCE_NOUNS.get(activity.cadence, activity.cadence)
    targets = (
        MemberTarget.objects.filter(membership__project=project, activity=activity)
        .select_related("membership__user")
        .order_by("membership__joined_at", "membership__pk")
    )
    for target in targets:
        name = target.membership.user.first_name or target.membership.user.username
        rows.append(
            {
                "key": f"{name}'s aiming for",
                "value": f"{target.target} a {cadence_noun}",
            }
        )
    rows.append(
        {
            "key": "Runs",
            "value": (
                f"Until {date_format(project.end_date, 'M j, Y')}"
                if project.end_date
                else "As long as you like"
            ),
        }
    )
    return rows


def _period_chip(activity, start, end):
    label = {
        Activity.Cadence.DAILY: "Today",
        Activity.Cadence.WEEKLY: "This week",
        Activity.Cadence.MONTHLY: "This month",
    }.get(activity.cadence, "This week")
    chip = {
        "label": label,
        "date_range": "",
        "time_left": _time_left_copy(activity.cadence, end),
    }
    if activity.cadence != Activity.Cadence.DAILY:
        display_end = end - timedelta(days=1)
        chip["date_range"] = (
            f"{date_format(timezone.localtime(start), 'M j')} – "
            f"{date_format(timezone.localtime(display_end), 'M j')}"
        )
    return chip


def _time_left_copy(cadence, end):
    seconds = max(0, (end - timezone.now()).total_seconds())
    if cadence == Activity.Cadence.DAILY:
        hours = max(1, int((seconds + 3599) // 3600))
        return "1 hour left" if hours == 1 else f"{hours} hours left"

    days = _days_left(cadence)
    return "1 day left" if days == 1 else f"{days} days left"


def _feed_title(cadence):
    return {
        Activity.Cadence.DAILY: "Today so far",
        Activity.Cadence.WEEKLY: "The week so far",
        Activity.Cadence.MONTHLY: "The month so far",
    }.get(cadence, "The week so far")


def _checkin_label(count):
    return "1 check-in" if count == 1 else f"{count} check-ins"


def _progress_with_display(progress, activity):
    return [_member_display(item, activity) for item in progress]


def _member_display(item, activity):
    next_item = dict(item)
    cadence_noun = CADENCE_NOUNS.get(activity.cadence, "week")
    done_copy = CADENCE_DONE_COPY.get(activity.cadence, "this week")
    period_short = {
        Activity.Cadence.DAILY: "today",
        Activity.Cadence.WEEKLY: "this week",
        Activity.Cadence.MONTHLY: "this month",
    }.get(activity.cadence, "this week")

    next_item["streak_badge"] = _streak_badge(activity.cadence, item["streak"], detail=True)
    if not item["target"]:
        next_item["status"] = {"class": "status-line", "text": "No target yet"}
    elif item["met"]:
        next_item["status"] = {"class": "status-line status-line--done", "text": f"Done for {done_copy} ✓"}
    elif item["is_current_user"]:
        remaining = item["target_count"] - item["count"]
        next_item["status"] = {
            "class": "status-line status-line--behind",
            "text": f"{remaining} more to hit your {cadence_noun} →",
        }
    else:
        remaining = item["target_count"] - item["count"]
        next_item["status"] = {"class": "status-line", "text": f"{remaining} to go {period_short}"}
    return next_item


def _streak_badge(cadence, streak, detail=False):
    if streak <= 0:
        text = {
            Activity.Cadence.DAILY: "New today",
            Activity.Cadence.WEEKLY: "New this week",
            Activity.Cadence.MONTHLY: "New this month",
        }.get(cadence, "New this week")
        return {"class": "streak streak--muted", "text": text}

    if cadence == Activity.Cadence.DAILY:
        text = f"🔥 Day {streak}"
    elif cadence == Activity.Cadence.MONTHLY:
        noun = "month" if streak == 1 else "months"
        text = f"🔥 {streak} {noun}"
        if detail:
            text = f"{text} strong"
    else:
        noun = "week" if streak == 1 else "weeks"
        text = f"🔥 {streak} {noun}"
        if detail:
            text = f"{text} strong"
    return {"class": "streak", "text": text}


def _project_feed(project, activity, current_user, progress, period_start, period_end, show_earlier):
    color_by_user = {item["user"].id: item["color"] for item in progress}
    current_events = list(
        EventLog.objects.filter(
            activity=activity,
            logged_at__gte=period_start,
            logged_at__lt=period_end,
        )
        .select_related("user")
        .prefetch_related("reactions__user")
    )
    current_nudges = list(
        Nudge.objects.filter(
            project=project,
            created_at__gte=period_start,
            created_at__lt=period_end,
        ).select_related("from_user", "to_user")
    )
    current_items = _render_feed_items(
        current_events,
        current_nudges,
        current_user,
        color_by_user,
        period_start,
    )

    older_events_qs = (
        EventLog.objects.filter(activity=activity, logged_at__lt=period_start)
        .select_related("user")
        .prefetch_related("reactions__user")
        .order_by("-logged_at")
    )
    older_nudges_qs = (
        Nudge.objects.filter(project=project, created_at__lt=period_start)
        .select_related("from_user", "to_user")
        .order_by("-created_at")
    )
    older_exists = older_events_qs.exists() or older_nudges_qs.exists()

    sections = [{"label": "", "items": current_items}] if current_items else []
    if show_earlier and older_exists:
        older_events = list(older_events_qs[:100])
        older_nudges = list(older_nudges_qs[:100])
        older_limit = max(0, 100 - len(current_items))
        older_items = _render_feed_items(
            older_events,
            older_nudges,
            current_user,
            color_by_user,
            period_start,
        )[:older_limit]
        previous_start, previous_end = get_period_bounds(
            activity.cadence,
            period_start - timedelta(microseconds=1),
        )
        previous_items = [
            item for item in older_items if previous_start <= item["sort_at"] < previous_end
        ]
        earlier_items = [
            item for item in older_items if item["sort_at"] < previous_start
        ]
        if previous_items:
            sections.append({"label": "Last week", "items": previous_items})
        if earlier_items:
            sections.append({"label": "Earlier", "items": earlier_items})

    return {
        "sections": sections,
        "empty": not current_items and not older_exists,
        "show_earlier_link": older_exists and not show_earlier,
        "checkin_count": len(current_events),
    }


def _render_feed_items(events, nudges, current_user, color_by_user, current_period_start):
    items = []
    for event in events:
        items.append(_event_feed_item(event, current_user, color_by_user, current_period_start))
    for nudge in nudges:
        items.append(_nudge_feed_item(nudge, current_user, current_period_start))
    items.sort(key=lambda item: item["sort_at"], reverse=True)
    return items


def _event_feed_item(event, current_user, color_by_user, current_period_start):
    reactions = {}
    for reaction in event.reactions.all():
        bucket = reactions.setdefault(
            reaction.emoji,
            {"emoji": reaction.emoji, "count": 0, "mine": False},
        )
        bucket["count"] += 1
        if reaction.user_id == current_user.id:
            bucket["mine"] = True

    return {
        "type": "event",
        "sort_at": event.logged_at,
        "display_name": _display_name(event.user, event.user_id == current_user.id),
        "initial": _display_name(event.user, event.user_id == current_user.id)[:1],
        "color": color_by_user.get(event.user_id, "sage"),
        "verb": f"logged a {event.activity.unit}",
        "timestamp": _feed_timestamp(event.logged_at, current_period_start),
        "note": event.note,
        "reactions": sorted(reactions.values(), key=lambda item: item["emoji"]),
    }


def _nudge_feed_item(nudge, current_user, current_period_start):
    return {
        "type": "nudge",
        "sort_at": nudge.created_at,
        "from_name": _display_name(nudge.from_user, nudge.from_user_id == current_user.id),
        "to_name": _display_name(nudge.to_user, nudge.to_user_id == current_user.id),
        "timestamp": _feed_timestamp(nudge.created_at, current_period_start),
    }


def _feed_timestamp(value, current_period_start):
    local_value = timezone.localtime(value)
    if value >= current_period_start:
        return date_format(local_value, "l, g:ia")
    return date_format(local_value, "M j")


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

    if activity and current and current["streak"] >= 2:
        return {
            "class": "pill--gold",
            "text": _streak_badge(activity.cadence, current["streak"])["text"],
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
            next_item["use_bar"] = target_count > 10
            if target_count > 10:
                next_item["dots"] = []
                next_item["overflow"] = 0
                next_item["bar_percent"] = min(100, int((item["count"] / target_count) * 100))
            else:
                dot_count = target_count
                filled = min(item["count"], dot_count)
                next_item["dots"] = [
                    {
                        "filled": index < filled,
                        "warn": bool(item["warn_next_dot"] and index == filled),
                    }
                    for index in range(dot_count)
                ]
                next_item["overflow"] = max(0, item["count"] - target_count)
                next_item["bar_percent"] = 0
        else:
            next_item["use_bar"] = False
            next_item["dots"] = []
            next_item["overflow"] = 0
            next_item["bar_percent"] = 0
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
