from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Activity, EventLog, MemberTarget, Membership, Project
from .utils import get_period_bounds


class CoreModelTests(TestCase):
    def test_project_activity_membership_target_and_event_relations(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="sam",
            email="sam@example.com",
            password="testpass123",
        )
        project = Project.objects.create(name="Study Group", created_by=user)
        activity = Activity.objects.create(
            project=project,
            name="Problem sets",
            unit="sets",
            cadence=Activity.Cadence.WEEKLY,
        )
        membership = Membership.objects.create(user=user, project=project)
        target = MemberTarget.objects.create(
            membership=membership,
            activity=activity,
            target=3,
        )
        event = EventLog.objects.create(activity=activity, user=user, note="Done")

        self.assertEqual(list(project.members.all()), [user])
        self.assertEqual(project.activities.first(), activity)
        self.assertEqual(membership.targets.first(), target)
        self.assertEqual(activity.event_logs.first(), event)
        self.assertEqual(user.event_logs.first(), event)

    def test_get_period_bounds_weekly_for_known_date(self):
        reference = timezone.make_aware(datetime(2026, 7, 1, 15, 30))

        start, end = get_period_bounds("weekly", reference)

        self.assertEqual(start, timezone.make_aware(datetime(2026, 6, 29, 0, 0)))
        self.assertEqual(end, timezone.make_aware(datetime(2026, 7, 6, 0, 0)))

    def test_project_invite_tokens_are_unique(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="alex",
            email="alex@example.com",
            password="testpass123",
        )

        first = Project.objects.create(name="First", created_by=user)
        second = Project.objects.create(name="Second", created_by=user)

        self.assertNotEqual(first.invite_token, second.invite_token)
