from django.db.models import Count

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


def _display_name(user, is_current_user=False):
    if is_current_user:
        return "You"
    return user.first_name or user.username


def project_member_progress(project, current_user):
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
                "color": "clay" if membership.user_id == current_user.id else "sage",
            }
            for membership in ordered_memberships
        ]

    start, end = get_period_bounds(activity.cadence)
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
                "color": color,
            }
        )

    if current_membership:
        target = targets.get(current_membership.id)
        count = counts.get(current_membership.user_id, 0)
        target_count = target.target if target else None
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
