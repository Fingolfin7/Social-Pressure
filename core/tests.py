from datetime import datetime
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .progress import project_member_progress
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


class ProjectFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="henry",
            email="henry@example.com",
            password="testpass123",
            first_name="Henry",
        )
        self.partner = User.objects.create_user(
            username="daniel",
            email="daniel@example.com",
            password="testpass123",
            first_name="Daniel",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def make_project(self, name="Gym Buddies"):
        project = Project.objects.create(name=name, created_by=self.user)
        activity = Activity.objects.create(
            project=project,
            name="Sessions",
            unit="session",
            cadence=Activity.Cadence.WEEKLY,
        )
        membership = Membership.objects.create(project=project, user=self.user)
        return project, activity, membership

    def test_create_post_makes_project_activity_creator_membership_and_redirects(self):
        response = self.client.post(
            reverse("project_create"),
            {
                "template": "custom",
                "name": "Writing Club",
                "activity": "Drafts",
                "unit": "draft",
                "cadence": "weekly",
                "duration": "open",
            },
        )

        project = Project.objects.get(name="Writing Club")
        self.assertRedirects(
            response,
            reverse("project_target", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )
        self.assertEqual(project.created_by, self.user)
        self.assertIsNone(project.end_date)
        self.assertEqual(project.activities.get().name, "Drafts")
        self.assertTrue(Membership.objects.filter(project=project, user=self.user).exists())

    def test_create_until_requires_end_date(self):
        response = self.client.post(
            reverse("project_create"),
            {
                "template": "custom",
                "name": "Writing Club",
                "activity": "Drafts",
                "unit": "draft",
                "cadence": "weekly",
                "duration": "until",
                "end_date": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the date you'll keep going until.")
        self.assertFalse(Project.objects.filter(name="Writing Club").exists())

    def test_target_post_creates_member_target_and_clamps_input(self):
        project, activity, membership = self.make_project()

        response = self.client.post(
            reverse("project_target", kwargs={"pk": project.pk}),
            {"target": "150"},
        )

        self.assertRedirects(
            response,
            reverse("project_detail", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )
        target = MemberTarget.objects.get(membership=membership, activity=activity)
        self.assertEqual(target.target, 99)

    def test_non_member_gets_404_on_project_detail_and_target(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        detail_response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        target_response = self.client.get(reverse("project_target", kwargs={"pk": project.pk}))

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(target_response.status_code, 404)

    def test_home_shows_behind_pill_and_orders_behind_project_first(self):
        behind_project, behind_activity, behind_membership = self.make_project("Behind Project")
        current_project, current_activity, current_membership = self.make_project("Current Project")
        Membership.objects.create(project=behind_project, user=self.partner)

        MemberTarget.objects.create(
            membership=behind_membership,
            activity=behind_activity,
            target=3,
        )
        MemberTarget.objects.create(
            membership=current_membership,
            activity=current_activity,
            target=1,
        )
        EventLog.objects.create(
            activity=behind_activity,
            user=self.user,
            logged_at=timezone.now(),
        )
        EventLog.objects.create(
            activity=current_activity,
            user=self.user,
            logged_at=timezone.now(),
        )

        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "You're 2 behind")
        self.assertLess(content.find("Behind Project"), content.find("Current Project"))

    def test_progress_colors_current_user_clay_and_first_partner_sage(self):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)

        progress = project_member_progress(project, self.user)

        self.assertEqual(progress[0]["display_name"], "You")
        self.assertEqual(progress[0]["color"], "clay")
        self.assertEqual(progress[1]["display_name"], "Daniel")
        self.assertEqual(progress[1]["color"], "sage")


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
