from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import EventLog, MemberTarget, Membership
from .utils import get_period_bounds


MEMBER_COLORS = ("sage", "plum", "blue")


def period_counts(activity, start, end):
    rows = (
        EventLog.objects.filter(activity=activity, logged_at__gte=start, logged_at__lt=end)
        .values("user_id")
        .annotate(count=Count("id"))
    )
    return {row["user_id"]: row["count"] for row in rows}


def member_streak(membership, activity, now=None):
    target = MemberTarget.objects.filter(
        membership=membership,
        activity=activity,
    ).first()
    if not target:
        return 0

    if now is None:
        now = timezone.now()

    streak = 0
    start, end = get_period_bounds(activity.cadence, now)
    target_count = target.target
    reference_date = start - timedelta(microseconds=1)

    current_count = EventLog.objects.filter(
        activity=activity,
        user=membership.user,
        logged_at__gte=start,
        logged_at__lt=end,
    ).count()
    if current_count >= target_count:
        streak = 1

    for _index in range(365):
        start, end = get_period_bounds(activity.cadence, reference_date)
        if end <= membership.joined_at:
            break

        count = EventLog.objects.filter(
            activity=activity,
            user=membership.user,
            logged_at__gte=start,
            logged_at__lt=end,
        ).count()
        if count < target_count:
            break

        streak += 1
        reference_date = start - timedelta(microseconds=1)

    return streak


def _display_name(user, is_current_user=False):
    if is_current_user:
        return "You"
    return user.first_name or user.username


def project_member_progress(project, current_user, now=None):
    if now is None:
        now = timezone.now()

    activity = project.activities.order_by("created_at", "pk").first()
    memberships = list(
        project.memberships.select_related("user").order_by("joined_at", "pk")
    )
    current_membership = None
    partners = []
    for membership in memberships:
        if membership.user_id == current_user.id:
            current_membership = membership
        else:
            partners.append(membership)

    ordered_memberships = ([current_membership] if current_membership else []) + partners
    if not activity:
        return [
            {
                "membership": membership,
                "user": membership.user,
                "display_name": _display_name(
                    membership.user, membership.user_id == current_user.id
                ),
                "is_current_user": membership.user_id == current_user.id,
                "count": 0,
                "target": None,
                "target_count": None,
                "met": False,
                "behind": False,
                "streak": 0,
                "warn_next_dot": False,
                "color": "clay" if membership.user_id == current_user.id else "sage",
            }
            for membership in ordered_memberships
        ]

    start, end = get_period_bounds(activity.cadence, now)
    counts = period_counts(activity, start, end)
    targets = {
        target.membership_id: target
        for target in MemberTarget.objects.filter(
            activity=activity,
            membership__in=memberships,
        )
    }

    progress = []
    for partner_index, membership in enumerate(partners):
        is_current_user = membership.user_id == current_user.id
        color = "clay" if is_current_user else MEMBER_COLORS[partner_index % len(MEMBER_COLORS)]
        target = targets.get(membership.id)
        count = counts.get(membership.user_id, 0)
        target_count = target.target if target else None
        period_elapsed = (now - start).total_seconds() / max(1, (end - start).total_seconds())
        progress.append(
            {
                "membership": membership,
                "user": membership.user,
                "display_name": _display_name(membership.user, is_current_user),
                "is_current_user": is_current_user,
                "count": count,
                "target": target,
                "target_count": target_count,
                "met": bool(target and count >= target.target),
                "behind": bool(target and count < target.target),
                "streak": member_streak(membership, activity, now),
                "warn_next_dot": bool(
                    is_current_user and target and count < target.target and period_elapsed > 0.6
                ),
                "color": color,
            }
        )

    if current_membership:
        target = targets.get(current_membership.id)
        count = counts.get(current_membership.user_id, 0)
        target_count = target.target if target else None
        period_elapsed = (now - start).total_seconds() / max(1, (end - start).total_seconds())
        progress.insert(
            0,
            {
                "membership": current_membership,
                "user": current_membership.user,
                "display_name": "You",
                "is_current_user": True,
                "count": count,
                "target": target,
                "target_count": target_count,
                "met": bool(target and count >= target.target),
                "behind": bool(target and count < target.target),
                "streak": member_streak(current_membership, activity, now),
                "warn_next_dot": bool(target and count < target.target and period_elapsed > 0.6),
                "color": "clay",
            },
        )

    return progress


def home_summary(user):
    partner_ids = set()
    memberships = (
        Membership.objects.filter(user=user)
        .select_related("project")
        .prefetch_related("project__activities", "project__memberships__user")
    )
    for membership in memberships:
        project = membership.project
        activity = project.activities.order_by("created_at", "pk").first()
        if not activity:
            continue

        target = MemberTarget.objects.filter(
            membership=membership,
            activity=activity,
        ).first()
        if not target:
            continue

        start, end = get_period_bounds(activity.cadence)
        count = (
            EventLog.objects.filter(
                activity=activity,
                user=user,
                logged_at__gte=start,
                logged_at__lt=end,
            ).count()
        )
        if count >= target.target:
            continue

        for partner in project.memberships.exclude(user=user):
            partner_ids.add(partner.user_id)

    return len(partner_ids)
