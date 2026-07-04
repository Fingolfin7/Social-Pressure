from datetime import datetime
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Activity, EventLog, MemberTarget, Membership, Project, PushSubscription
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


class PushViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="pushuser",
            email="push@example.com",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_subscribe_creates_push_subscription(self):
        response = self.client.post(
            "/push/subscribe/",
            data=json.dumps(
                {
                    "endpoint": "https://push.example/subscription",
                    "keys": {
                        "p256dh": "public-key",
                        "auth": "auth-secret",
                    },
                }
            ),
            content_type="application/json",
            HTTP_USER_AGENT="Django test client",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        subscription = PushSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.endpoint, "https://push.example/subscription")
        self.assertEqual(subscription.p256dh, "public-key")
        self.assertEqual(subscription.auth, "auth-secret")
        self.assertEqual(subscription.user_agent, "Django test client")

    @override_settings(
        VAPID_PRIVATE_KEY="private-key",
        VAPID_PUBLIC_KEY="public-key",
        VAPID_ADMIN_EMAIL="admin@example.com",
    )
    @patch("core.views.send_push_to_user", return_value=1)
    def test_push_test_returns_sent_count(self, send_push_to_user):
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example/subscription",
            p256dh="public-key",
            auth="auth-secret",
        )

        response = self.client.post(
            "/push/test/",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"sent": 1})
        send_push_to_user.assert_called_once()


class PwaViewTests(TestCase):
    def test_manifest_returns_manifest_json(self):
        response = self.client.get("/manifest.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertEqual(response.json()["name"], "Social Pressure")

    def test_service_worker_returns_allowed_header(self):
        response = self.client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
