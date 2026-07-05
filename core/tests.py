from datetime import datetime, timedelta
import json
import os
import shutil
import tempfile
from urllib.parse import quote
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .progress import member_streak, project_member_progress
from .models import (
    Activity,
    EventLog,
    MemberTarget,
    Membership,
    Nudge,
    Project,
    PushSubscription,
    Reaction,
)
from .utils import get_period_bounds
from .views import ALLOWED_REACTIONS


TINY_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


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

    def test_subscribe_moves_existing_endpoint_from_other_user(self):
        User = get_user_model()
        other_user = User.objects.create_user(
            username="otherpush",
            email="otherpush@example.com",
            password="testpass123",
        )
        endpoint = "https://push.example/shared-subscription"
        PushSubscription.objects.create(
            user=other_user,
            endpoint=endpoint,
            p256dh="old-public-key",
            auth="old-auth-secret",
        )

        response = self.client.post(
            "/push/subscribe/",
            data=json.dumps(
                {
                    "endpoint": endpoint,
                    "keys": {
                        "p256dh": "new-public-key",
                        "auth": "new-auth-secret",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=other_user, endpoint=endpoint).exists())
        subscription = PushSubscription.objects.get(user=self.user, endpoint=endpoint)
        self.assertEqual(subscription.p256dh, "new-public-key")
        self.assertEqual(subscription.auth, "new-auth-secret")

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


class UserProfileTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="henry",
            email="profile@example.com",
            password="testpass123",
            first_name="Henry",
        )
        self.client.force_login(self.user)

    def test_profile_get_renders_form(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This is you.")
        self.assertContains(response, "Your name")
        self.assertContains(response, "What partners see.")

    def test_profile_post_updates_first_name_and_redirects(self):
        response = self.client.post(reverse("profile"), {"first_name": "Hank"})

        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Hank")

    def test_profile_post_uploads_small_avatar_file(self):
        media_root = tempfile.mkdtemp()
        try:
            with self.settings(MEDIA_ROOT=media_root):
                upload = SimpleUploadedFile(
                    "avatar.gif",
                    TINY_GIF,
                    content_type="image/gif",
                )

                response = self.client.post(
                    reverse("profile"),
                    {"first_name": "Henry", "avatar": upload},
                )

                self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar.name.startswith("avatars/"))
                self.assertTrue(os.path.exists(os.path.join(media_root, self.user.avatar.name)))
        finally:
            shutil.rmtree(media_root)

    def test_profile_rejects_oversized_avatar(self):
        upload = SimpleUploadedFile(
            "huge.jpg",
            b"x" * (6 * 1024 * 1024),
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("profile"),
            {"first_name": "Henry", "avatar": upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That photo&#x27;s too big — 5 MB max.")
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_profile_remove_photo_clears_avatar_and_deletes_file(self):
        media_root = tempfile.mkdtemp()
        try:
            with self.settings(MEDIA_ROOT=media_root):
                self.user.avatar.save("old.gif", ContentFile(TINY_GIF), save=True)
                old_path = os.path.join(media_root, self.user.avatar.name)
                self.assertTrue(os.path.exists(old_path))

                response = self.client.post(
                    reverse("profile"),
                    {"first_name": "Henry", "remove_photo": "on"},
                )

                self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
                self.user.refresh_from_db()
                self.assertFalse(self.user.avatar)
                self.assertFalse(os.path.exists(old_path))
        finally:
            shutil.rmtree(media_root)


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

    def move_joined_at(self, membership, value):
        Membership.objects.filter(pk=membership.pk).update(joined_at=value)
        membership.refresh_from_db()

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

    def test_create_recap_uses_activity_unit_and_cadence(self):
        response = self.client.get(reverse("project_create"))
        content = response.content.decode()

        self.assertIn("<span data-recap-activity>sessions</span>", content)
        self.assertIn("<span data-recap-unit>session</span>", content)
        self.assertIn("<span data-recap-cadence>week</span>", content)
        self.assertIn("<span data-recap-duration>for as long as you both keep it up</span>", content)

    def test_create_post_rerender_recap_uses_posted_values_and_valid_until_date(self):
        response = self.client.post(
            reverse("project_create"),
            {
                "template": "custom",
                "name": "",
                "activity": "Features",
                "unit": "feature",
                "cadence": "daily",
                "duration": "until",
                "end_date": "2099-09-30",
            },
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("<span data-recap-activity>features</span>", content)
        self.assertIn("<span data-recap-unit>feature</span>", content)
        self.assertIn("<span data-recap-cadence>day</span>", content)
        self.assertContains(response, "until Sep 30, 2099")

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

    def test_join_get_as_non_member_renders_project_inviter_and_default_target(self):
        project, activity, membership = self.make_project()
        MemberTarget.objects.create(membership=membership, activity=activity, target=4)
        self.client.force_login(self.partner)

        response = self.client.get(reverse("project_join", kwargs={"token": project.invite_token}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gym Buddies")
        self.assertContains(response, "Henry")
        self.assertContains(response, 'data-stepper-value>4</div>', html=False)

    def test_join_post_creates_membership_and_clamped_target(self):
        project, activity, _membership = self.make_project()
        self.client.force_login(self.partner)

        response = self.client.post(
            reverse("project_join", kwargs={"token": project.invite_token}),
            {"target": "150"},
        )

        self.assertRedirects(
            response,
            reverse("project_detail", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )
        membership = Membership.objects.get(project=project, user=self.partner)
        self.assertEqual(
            MemberTarget.objects.get(membership=membership, activity=activity).target,
            99,
        )

    def test_join_post_twice_does_not_duplicate_membership_or_target(self):
        project, activity, _membership = self.make_project()
        self.client.force_login(self.partner)
        url = reverse("project_join", kwargs={"token": project.invite_token})

        first_response = self.client.post(url, {"target": "5"})
        second_response = self.client.post(url, {"target": "5"})

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(Membership.objects.filter(project=project, user=self.partner).count(), 1)
        membership = Membership.objects.get(project=project, user=self.partner)
        self.assertEqual(MemberTarget.objects.filter(membership=membership, activity=activity).count(), 1)

    def test_join_get_redirects_when_already_member(self):
        project, _activity, _membership = self.make_project()

        response = self.client.get(reverse("project_join", kwargs={"token": project.invite_token}))

        self.assertRedirects(
            response,
            reverse("project_detail", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )

    def test_join_bad_token_returns_404(self):
        response = self.client.get(reverse("project_join", kwargs={"token": uuid.uuid4()}))

        self.assertEqual(response.status_code, 404)

    def test_logged_out_join_redirects_to_login_with_next(self):
        project, _activity, _membership = self.make_project()
        self.client.logout()
        join_url = reverse("project_join", kwargs={"token": project.invite_token})

        response = self.client.get(join_url)

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={join_url}",
            fetch_redirect_response=False,
        )

    def test_register_honors_safe_next(self):
        self.client.logout()
        next_url = "/projects/new/"

        response = self.client.post(
            f"{reverse('register')}?next={next_url}",
            {
                "username": "newperson",
                "email": "newperson@example.com",
                "password1": "testpass123",
                "password2": "testpass123",
                "next": next_url,
            },
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_project_detail_shows_invite_reminder_when_solo_only(self):
        project, _activity, _membership = self.make_project()

        solo_response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        Membership.objects.create(project=project, user=self.partner)
        partner_response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(solo_response, "It's just you so far.")
        self.assertContains(solo_response, "Copy invite link")
        self.assertNotContains(partner_response, "It's just you so far.")

    def test_project_detail_includes_join_url_for_copy_button(self):
        project, _activity, _membership = self.make_project()
        join_path = reverse("project_join", kwargs={"token": project.invite_token})

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, join_path)
        self.assertContains(response, 'data-copy-text="http://testserver')

    def test_project_detail_solo_invite_share_links(self):
        project, _activity, _membership = self.make_project()
        invite_url = f"http://testserver{reverse('project_join', kwargs={'token': project.invite_token})}"
        encoded_invite_url = quote(invite_url, safe="/")

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, "https://wa.me")
        self.assertContains(response, "twitter.com/intent/tweet")
        self.assertContains(response, "sms:?body=")
        self.assertContains(response, "fb-messenger://share")
        self.assertContains(response, "data-share-native")
        self.assertContains(response, encoded_invite_url)
        self.assertContains(response, "M17.472 14.382")

    def test_project_detail_partner_project_omits_invite_share_row(self):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertNotContains(response, "share-row")
        self.assertNotContains(response, "https://wa.me")
        self.assertNotContains(response, "twitter.com/intent/tweet")
        self.assertNotContains(response, "sms:?body=")
        self.assertNotContains(response, "fb-messenger://share")
        self.assertNotContains(response, "data-share-native")

    def test_project_detail_links_to_project_settings(self):
        project, _activity, _membership = self.make_project()

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, 'aria-label="Project settings"')
        self.assertContains(response, reverse("project_settings", kwargs={"pk": project.pk}))
        self.assertContains(response, "M12 5.5h.01M12 12h.01M12 18.5h.01")

    def test_project_settings_visibility_and_invite_copy(self):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)

        creator_response = self.client.get(reverse("project_settings", kwargs={"pk": project.pk}))

        self.assertContains(creator_response, "Leave this project")
        self.assertContains(creator_response, "Delete this project")
        self.assertContains(creator_response, "Copy invite link")
        self.assertContains(creator_response, 'data-copy-text="http://testserver')
        self.assertContains(creator_response, "share-row")
        self.assertContains(creator_response, "Sessions")
        self.assertContains(creator_response, "weekly")
        self.assertContains(creator_response, "2 members")

        self.client.force_login(self.partner)
        member_response = self.client.get(reverse("project_settings", kwargs={"pk": project.pk}))

        self.assertContains(member_response, "Leave this project")
        self.assertNotContains(member_response, "Delete this project")
        self.assertContains(member_response, "Copy invite link")

    def test_project_settings_non_member_gets_404(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        response = self.client.get(reverse("project_settings", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)

    def test_member_leave_deletes_membership_targets_keeps_events_and_messages(self):
        project, activity, membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        target = MemberTarget.objects.create(membership=membership, activity=activity, target=3)
        event = EventLog.objects.create(activity=activity, user=self.user)

        response = self.client.post(reverse("project_leave", kwargs={"pk": project.pk}))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Membership.objects.filter(project=project, user=self.user).exists())
        self.assertFalse(MemberTarget.objects.filter(pk=target.pk).exists())
        self.assertTrue(EventLog.objects.filter(pk=event.pk).exists())
        project.refresh_from_db()
        self.assertIsNone(project.created_by)
        self.assertEqual(
            [str(message) for message in get_messages(response.wsgi_request)],
            ["You left Gym Buddies."],
        )

    def test_last_member_leave_deletes_project(self):
        project, _activity, _membership = self.make_project()

        response = self.client.post(reverse("project_leave", kwargs={"pk": project.pk}))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_project_leave_non_member_gets_404(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        response = self.client.post(reverse("project_leave", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_creator_delete_removes_project_activities_events_and_messages(self):
        project, activity, _membership = self.make_project()
        EventLog.objects.create(activity=activity, user=self.user)

        response = self.client.post(reverse("project_delete", kwargs={"pk": project.pk}))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        self.assertFalse(Activity.objects.filter(pk=activity.pk).exists())
        self.assertFalse(EventLog.objects.filter(activity=activity).exists())
        self.assertEqual(
            [str(message) for message in get_messages(response.wsgi_request)],
            ["Gym Buddies is gone."],
        )

    def test_project_delete_non_creator_member_gets_404_and_project_stays(self):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        self.client.force_login(self.partner)

        response = self.client.post(reverse("project_delete", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_project_delete_non_member_gets_404(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        response = self.client.post(reverse("project_delete", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_project_detail_includes_bottom_bar_log_link(self):
        project, activity, _membership = self.make_project()

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, 'class="bottom-bar"')
        self.assertContains(response, reverse("event_log", kwargs={"pk": project.pk}))
        self.assertContains(response, f"Log a {activity.unit}")

    def test_project_detail_includes_live_sync_attributes(self):
        project, _activity, _membership = self.make_project()

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, "data-live-root")
        self.assertContains(response, 'data-live="members"')
        self.assertContains(response, 'data-live="feed"')
        self.assertContains(response, f'data-live-url="{reverse("project_version", kwargs={"pk": project.pk})}"')

    def test_project_detail_renders_avatar_image_or_initial(self):
        media_root = tempfile.mkdtemp()
        try:
            with self.settings(MEDIA_ROOT=media_root):
                self.user.avatar.save("henry.gif", ContentFile(TINY_GIF), save=True)
                project, _activity, _membership = self.make_project()
                Membership.objects.create(project=project, user=self.partner)

                response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
                content = response.content.decode()

                self.assertIn('<span class="avatar avatar--46 avatar--clay"><img', content)
                self.assertIn(self.user.avatar.url, content)
                self.assertIn('<span class="avatar avatar--46 avatar--sage">D</span>', content)
        finally:
            shutil.rmtree(media_root)

    @override_settings(VAPID_PUBLIC_KEY="test-public-key")
    def test_project_detail_includes_push_banner_with_public_key(self):
        project, _activity, _membership = self.make_project()

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, "data-push-banner")
        self.assertContains(response, 'data-vapid-public-key="test-public-key"')
        self.assertContains(response, "Get a ping when your partners check in.")

    def test_home_includes_push_card_and_base_push_script(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "data-push-controls")
        self.assertNotContains(response, "data-push-banner")
        self.assertContains(response, "core/js/push.js")

    def test_base_topbar_avatar_links_to_profile_and_uses_username_before_email(self):
        User = get_user_model()
        avatar_user = User.objects.create_user(
            username="Helen",
            email="robert@example.com",
            password="testpass123",
        )
        self.client.force_login(avatar_user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, f'href="{reverse("profile")}"')
        self.assertContains(response, 'aria-label="Profile"')
        self.assertContains(response, 'avatar--34 avatar--clay">H</span>', html=False)
        self.assertNotContains(response, 'avatar--34 avatar--clay">r</span>', html=False)
        self.assertNotContains(response, f'href="{reverse("logout")}"')

    def test_project_version_changes_for_feed_data(self):
        project, activity, _membership = self.make_project()
        version_url = reverse("project_version", kwargs={"pk": project.pk})

        response = self.client.get(version_url)
        self.assertEqual(response.status_code, 200)
        initial_version = response.json()["version"]
        self.assertIsInstance(initial_version, str)

        event = EventLog.objects.create(activity=activity, user=self.user)
        event_version = self.client.get(version_url).json()["version"]
        self.assertNotEqual(event_version, initial_version)

        Nudge.objects.create(project=project, from_user=self.user, to_user=self.partner)
        nudge_version = self.client.get(version_url).json()["version"]
        self.assertNotEqual(nudge_version, event_version)

        Reaction.objects.create(event=event, user=self.partner, emoji="ðŸ‘")
        reaction_version = self.client.get(version_url).json()["version"]
        self.assertNotEqual(reaction_version, nudge_version)

        event.delete()
        deleted_version = self.client.get(version_url).json()["version"]
        self.assertNotEqual(deleted_version, reaction_version)

    def test_project_version_non_member_gets_404(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        response = self.client.get(reverse("project_version", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)

    @patch("core.views.send_push_to_user", return_value=1)
    def test_event_log_post_creates_event_pushes_partners_and_redirects(self, send_push_to_user):
        project, activity, membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        MemberTarget.objects.create(membership=membership, activity=activity, target=3)
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example/logger",
            p256dh="public-key",
            auth="auth-secret",
        )
        PushSubscription.objects.create(
            user=self.partner,
            endpoint="https://push.example/partner",
            p256dh="public-key",
            auth="auth-secret",
        )

        response = self.client.post(
            reverse("event_log", kwargs={"pk": project.pk}),
            {"note": "Done before work"},
        )

        event = EventLog.objects.get(activity=activity, user=self.user)
        self.assertEqual(event.note, "Done before work")
        self.assertRedirects(
            response,
            f"{reverse('event_logged', kwargs={'pk': project.pk, 'event_pk': event.pk})}?partners=1",
            fetch_redirect_response=False,
        )
        send_push_to_user.assert_called_once()
        push_user, payload = send_push_to_user.call_args.args
        self.assertEqual(push_user, self.partner)
        self.assertEqual(payload["title"], project.name)
        self.assertIn("Henry", payload["body"])
        self.assertIn("1/3", payload["body"])
        self.assertIn(reverse("project_detail", kwargs={"pk": project.pk}), payload["url"])

    @patch("core.views.send_push_to_user", side_effect=Exception("push failed"))
    def test_event_log_push_exception_does_not_break_response(self, send_push_to_user):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)

        response = self.client.post(reverse("event_log", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(EventLog.objects.count(), 1)
        send_push_to_user.assert_called_once()

    def test_event_logged_copy_shows_hit_and_to_go_states(self):
        hit_project, hit_activity, hit_membership = self.make_project("Hit Project")
        MemberTarget.objects.create(membership=hit_membership, activity=hit_activity, target=3)
        start, _end = get_period_bounds(hit_activity.cadence)
        EventLog.objects.create(activity=hit_activity, user=self.user, logged_at=start + timedelta(hours=9))
        EventLog.objects.create(activity=hit_activity, user=self.user, logged_at=start + timedelta(hours=10))
        hit_event = EventLog.objects.create(
            activity=hit_activity,
            user=self.user,
            logged_at=start + timedelta(hours=11),
        )

        hit_response = self.client.get(
            reverse("event_logged", kwargs={"pk": hit_project.pk, "event_pk": hit_event.pk})
        )

        self.assertContains(hit_response, "you hit it")
        self.assertContains(hit_response, "3 of 3")

        under_project, under_activity, under_membership = self.make_project("Under Project")
        MemberTarget.objects.create(membership=under_membership, activity=under_activity, target=3)
        under_start, _under_end = get_period_bounds(under_activity.cadence)
        EventLog.objects.create(
            activity=under_activity,
            user=self.user,
            logged_at=under_start + timedelta(hours=9),
        )
        under_event = EventLog.objects.create(
            activity=under_activity,
            user=self.user,
            logged_at=under_start + timedelta(hours=10),
        )

        under_response = self.client.get(
            reverse("event_logged", kwargs={"pk": under_project.pk, "event_pk": under_event.pk})
        )

        self.assertContains(under_response, "one to go")
        self.assertContains(under_response, "2 of 3")

    def test_event_undo_within_two_minutes_deletes_and_redirects(self):
        project, activity, _membership = self.make_project()
        event = EventLog.objects.create(activity=activity, user=self.user)

        response = self.client.post(
            reverse("event_undo", kwargs={"pk": project.pk, "event_pk": event.pk})
        )

        self.assertRedirects(
            response,
            reverse("project_detail", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )
        self.assertFalse(EventLog.objects.filter(pk=event.pk).exists())

    def test_event_undo_after_two_minutes_does_not_delete(self):
        project, activity, _membership = self.make_project()
        event = EventLog.objects.create(activity=activity, user=self.user)
        EventLog.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(minutes=3)
        )

        response = self.client.post(
            reverse("event_undo", kwargs={"pk": project.pk, "event_pk": event.pk})
        )

        self.assertRedirects(
            response,
            reverse("project_detail", kwargs={"pk": project.pk}),
            fetch_redirect_response=False,
        )
        self.assertTrue(EventLog.objects.filter(pk=event.pk).exists())

    def test_non_member_gets_404_on_event_log_get_and_post(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)
        url = reverse("event_log", kwargs={"pk": project.pk})

        get_response = self.client.get(url)
        post_response = self.client.post(url)

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)

    def test_non_owner_gets_404_on_event_logged(self):
        project, activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        event = EventLog.objects.create(activity=activity, user=self.user)
        self.client.force_login(self.partner)

        response = self.client.get(
            reverse("event_logged", kwargs={"pk": project.pk, "event_pk": event.pk})
        )

        self.assertEqual(response.status_code, 404)

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

    def test_member_streak_counts_previous_periods_when_current_unmet(self):
        now = timezone.make_aware(datetime(2026, 7, 3, 12, 0))
        project, activity, membership = self.make_project()
        MemberTarget.objects.create(membership=membership, activity=activity, target=2)
        current_start, _current_end = get_period_bounds(activity.cadence, now)
        previous_start, _previous_end = get_period_bounds(
            activity.cadence,
            current_start - timedelta(microseconds=1),
        )
        two_back_start, _two_back_end = get_period_bounds(
            activity.cadence,
            previous_start - timedelta(microseconds=1),
        )
        self.move_joined_at(membership, two_back_start - timedelta(days=1))

        for logged_at in (
            previous_start + timedelta(hours=9),
            previous_start + timedelta(hours=10),
            two_back_start + timedelta(hours=9),
            two_back_start + timedelta(hours=10),
        ):
            EventLog.objects.create(activity=activity, user=self.user, logged_at=logged_at)

        self.assertEqual(member_streak(membership, activity, now), 2)

    def test_member_streak_stops_at_broken_previous_period(self):
        now = timezone.make_aware(datetime(2026, 7, 3, 12, 0))
        project, activity, membership = self.make_project()
        MemberTarget.objects.create(membership=membership, activity=activity, target=2)
        current_start, _current_end = get_period_bounds(activity.cadence, now)
        previous_start, _previous_end = get_period_bounds(
            activity.cadence,
            current_start - timedelta(microseconds=1),
        )
        two_back_start, _two_back_end = get_period_bounds(
            activity.cadence,
            previous_start - timedelta(microseconds=1),
        )
        self.move_joined_at(membership, two_back_start - timedelta(days=1))

        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=previous_start + timedelta(hours=9),
        )
        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=two_back_start + timedelta(hours=9),
        )
        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=two_back_start + timedelta(hours=10),
        )

        self.assertEqual(member_streak(membership, activity, now), 0)

    def test_member_streak_is_zero_without_target(self):
        now = timezone.make_aware(datetime(2026, 7, 3, 12, 0))
        _project, activity, membership = self.make_project()

        self.assertEqual(member_streak(membership, activity, now), 0)

    def test_warn_next_dot_only_for_current_user_late_and_behind(self):
        project, activity, membership = self.make_project()
        partner_membership = Membership.objects.create(project=project, user=self.partner)
        MemberTarget.objects.create(membership=membership, activity=activity, target=3)
        MemberTarget.objects.create(membership=partner_membership, activity=activity, target=3)
        late_now = timezone.make_aware(datetime(2026, 7, 5, 18, 0))
        early_now = timezone.make_aware(datetime(2026, 6, 30, 9, 0))

        late_progress = project_member_progress(project, self.user, now=late_now)
        early_progress = project_member_progress(project, self.user, now=early_now)

        self.assertTrue(late_progress[0]["warn_next_dot"])
        self.assertFalse(late_progress[1]["warn_next_dot"])
        self.assertFalse(early_progress[0]["warn_next_dot"])

    def test_project_detail_renders_partner_event_and_grouped_reactions(self):
        project, activity, membership = self.make_project()
        partner_membership = Membership.objects.create(project=project, user=self.partner)
        MemberTarget.objects.create(membership=membership, activity=activity, target=3)
        MemberTarget.objects.create(membership=partner_membership, activity=activity, target=3)
        start, _end = get_period_bounds(activity.cadence)
        event = EventLog.objects.create(
            activity=activity,
            user=self.partner,
            logged_at=start + timedelta(hours=10),
            note="Leg day done",
        )
        Reaction.objects.create(event=event, user=self.user, emoji="👏")
        Reaction.objects.create(event=event, user=self.partner, emoji="👏")

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        content = response.content.decode()

        self.assertContains(response, "Daniel")
        self.assertContains(response, "logged a session")
        self.assertContains(response, "Leg day done")
        self.assertContains(response, "👏")
        self.assertIn('<span class="reaction-pill__count">2</span>', content)
        self.assertIn("reaction-pill--mine", content)

    def test_event_react_toggles_add_and_remove(self):
        project, activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        event = EventLog.objects.create(activity=activity, user=self.partner)
        url = reverse("event_react", kwargs={"event_pk": event.pk})

        add_response = self.client.post(
            url,
            data=json.dumps({"emoji": "👏"}),
            content_type="application/json",
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(Reaction.objects.filter(event=event, user=self.user, emoji="👏").count(), 1)
        self.assertContains(add_response, 'data-reaction-row')
        self.assertContains(add_response, 'reaction-pill--mine')
        self.assertContains(add_response, '<span class="reaction-pill__count">1</span>', html=False)

        remove_response = self.client.post(
            url,
            data=json.dumps({"emoji": "👏"}),
            content_type="application/json",
        )

        self.assertEqual(remove_response.status_code, 200)
        self.assertFalse(Reaction.objects.filter(event=event, user=self.user, emoji="👏").exists())
        self.assertContains(remove_response, 'data-reaction-add')

    def test_event_react_accepts_expanded_emoji(self):
        project, activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        event = EventLog.objects.create(activity=activity, user=self.partner)

        response = self.client.post(
            reverse("event_react", kwargs={"event_pk": event.pk}),
            data=json.dumps({"emoji": "👀"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reaction.objects.filter(event=event, user=self.user, emoji="👀").exists())

    def test_event_react_rejects_invalid_emoji(self):
        project, activity, _membership = self.make_project()
        event = EventLog.objects.create(activity=activity, user=self.user)

        response = self.client.post(
            reverse("event_react", kwargs={"event_pk": event.pk}),
            data=json.dumps({"emoji": "🦄"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reaction.objects.exists())

    def test_allowed_reactions_fit_database_field(self):
        self.assertTrue(all(len(emoji) <= 8 for emoji in ALLOWED_REACTIONS))

    def test_event_react_non_member_gets_404(self):
        project, activity, _membership = self.make_project()
        event = EventLog.objects.create(activity=activity, user=self.user)
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("event_react", kwargs={"event_pk": event.pk}),
            data=json.dumps({"emoji": "👏"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_project_detail_reaction_add_pill_present_without_reactions(self):
        project, activity, _membership = self.make_project()
        EventLog.objects.create(activity=activity, user=self.user)

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))

        self.assertContains(response, 'data-reaction-add')
        self.assertContains(response, reverse("event_react", kwargs={"event_pk": EventLog.objects.get().pk}))

    @patch("core.views.send_push_to_user", return_value=1)
    def test_project_nudge_creates_one_per_partner_and_pushes_each(self, send_push_to_user):
        User = get_user_model()
        second_partner = User.objects.create_user(
            username="maya",
            email="maya@example.com",
            password="testpass123",
            first_name="Maya",
        )
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        Membership.objects.create(project=project, user=second_partner)

        response = self.client.post(
            reverse("project_nudge", kwargs={"pk": project.pk}),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "sent": 2})
        self.assertEqual(Nudge.objects.filter(project=project, from_user=self.user).count(), 2)
        self.assertEqual(send_push_to_user.call_count, 2)
        pushed_users = {call.args[0] for call in send_push_to_user.call_args_list}
        self.assertEqual(pushed_users, {self.partner, second_partner})
        _recipient, payload = send_push_to_user.call_args.args
        self.assertEqual(payload["title"], project.name)
        self.assertEqual(payload["body"], "Henry nudged you — your turn 👀")
        self.assertIn(reverse("project_detail", kwargs={"pk": project.pk}), payload["url"])

    @patch("core.views.send_push_to_user", return_value=1)
    def test_project_nudge_twice_same_day_creates_rows_each_time(self, send_push_to_user):
        project, _activity, _membership = self.make_project()
        Membership.objects.create(project=project, user=self.partner)
        url = reverse("project_nudge", kwargs={"pk": project.pk})

        first_response = self.client.post(url, data=json.dumps({}), content_type="application/json")
        second_response = self.client.post(url, data=json.dumps({}), content_type="application/json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json(), {"ok": True, "sent": 1})
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json(), {"ok": True, "sent": 1})
        self.assertEqual(Nudge.objects.filter(project=project, from_user=self.user).count(), 2)
        self.assertEqual(send_push_to_user.call_count, 2)

    def test_project_detail_renders_nudge_button_enabled_and_absent(self):
        solo_project, _solo_activity, _solo_membership = self.make_project("Solo")
        solo_response = self.client.get(reverse("project_detail", kwargs={"pk": solo_project.pk}))
        self.assertNotContains(solo_response, 'data-nudge')

        project, _activity, _membership = self.make_project("Partners")
        Membership.objects.create(project=project, user=self.partner)
        nudge_url = reverse("project_nudge", kwargs={"pk": project.pk})

        enabled_response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        self.assertContains(enabled_response, 'data-nudge')
        self.assertContains(enabled_response, f'data-nudge-url="{nudge_url}"')
        self.assertContains(enabled_response, 'aria-label="Nudge Daniel"')

        Nudge.objects.create(project=project, from_user=self.user, to_user=self.partner)
        still_enabled_response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        self.assertContains(still_enabled_response, 'class="nudge-btn"')
        self.assertNotContains(still_enabled_response, "is-disabled")

    def test_project_nudge_non_member_gets_404(self):
        project, _activity, _membership = self.make_project()
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("project_nudge", kwargs={"pk": project.pk}),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_project_detail_show_earlier_reveals_previous_period_event(self):
        project, activity, membership = self.make_project()
        MemberTarget.objects.create(membership=membership, activity=activity, target=3)
        current_start, _current_end = get_period_bounds(activity.cadence)
        previous_start, _previous_end = get_period_bounds(
            activity.cadence,
            current_start - timedelta(microseconds=1),
        )
        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=previous_start + timedelta(hours=12),
            note="Older session",
        )

        response = self.client.get(reverse("project_detail", kwargs={"pk": project.pk}))
        self.assertContains(response, "Show earlier")
        self.assertNotContains(response, "Older session")

        earlier_response = self.client.get(
            f"{reverse('project_detail', kwargs={'pk': project.pk})}?earlier=1"
        )
        self.assertContains(earlier_response, "Last week")
        self.assertContains(earlier_response, "Older session")

    def test_home_shows_gold_streak_pill_when_current_user_on_streak(self):
        project, activity, membership = self.make_project("Streak Project")
        MemberTarget.objects.create(membership=membership, activity=activity, target=1)
        current_start, _current_end = get_period_bounds(activity.cadence)
        previous_start, _previous_end = get_period_bounds(
            activity.cadence,
            current_start - timedelta(microseconds=1),
        )
        self.move_joined_at(membership, previous_start - timedelta(days=1))
        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=current_start + timedelta(hours=9),
        )
        EventLog.objects.create(
            activity=activity,
            user=self.user,
            logged_at=previous_start + timedelta(hours=9),
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, "🔥 2 weeks")
        self.assertContains(response, "pill--gold")


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
