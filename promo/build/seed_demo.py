"""Seed an isolated demo database for the promo video recording."""
import os
import sys
from datetime import datetime, timedelta

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEMO_DB = os.path.join(SCRATCH, "demo.sqlite3").replace("\\", "/")

os.environ["DATABASE_URL"] = f"sqlite:///{DEMO_DB}"
os.environ["DJANGO_DEBUG"] = "1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "socialpressure.settings")

sys.path.insert(0, r"C:\Users\mushu\Documents\Programming\Python\Social Pressure")

import django

django.setup()

from django.core.management import call_command
from django.utils import timezone
import zoneinfo

call_command("migrate", verbosity=0)
call_command("flush", interactive=False, verbosity=0)

from django.contrib.auth import get_user_model
from core.models import (
    Activity,
    EventLog,
    MemberTarget,
    Membership,
    Nudge,
    Project,
    Reaction,
)

User = get_user_model()
TZ = zoneinfo.ZoneInfo("Europe/Prague")


def dt(day, hour, minute=0):
    """Aware datetime for a given date at hour:minute local time."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


PASSWORD = "demo-pass-1234"

alex = User.objects.create_user(
    username="alex", email="alex@example.com", password=PASSWORD, first_name="Alex"
)
maya = User.objects.create_user(
    username="maya", email="maya@example.com", password=PASSWORD, first_name="Maya"
)
# Fresh account (also displays as "Alex") for the create/invite/join scenes.
alex2 = User.objects.create_user(
    username="alexj", email="alexj@example.com", password=PASSWORD, first_name="Alex"
)

now = timezone.now().astimezone(TZ)
today = now.date()
week_start = today - timedelta(days=today.weekday())  # Monday of current week

project = Project.objects.create(name="Gym Buddies", created_by=alex)
activity = Activity.objects.create(
    project=project, name="Sessions", unit="session", cadence="weekly"
)

m_alex = Membership.objects.create(project=project, user=alex)
m_maya = Membership.objects.create(project=project, user=maya)
joined = dt(week_start - timedelta(weeks=4), 18, 30)
Membership.objects.filter(pk=m_alex.pk).update(joined_at=joined)
Membership.objects.filter(pk=m_maya.pk).update(joined_at=joined + timedelta(hours=3))

MemberTarget.objects.create(membership=m_alex, activity=activity, target=4)
MemberTarget.objects.create(membership=m_maya, activity=activity, target=3)

# (weekday, hour, minute, note) per user per week.
alex_week = [
    (0, 7, 10, ""),
    (2, 18, 40, "leg day, pray for me"),
    (4, 17, 5, ""),
    (5, 10, 20, "weekend make-up session"),
]
maya_week = [
    (1, 6, 45, "early bird gets the gains"),
    (3, 19, 15, ""),
    (5, 9, 30, ""),
]

events = []
for weeks_ago in (3, 2, 1):
    monday = week_start - timedelta(weeks=weeks_ago)
    for wd, h, mi, note in alex_week:
        events.append(EventLog(activity=activity, user=alex,
                               logged_at=dt(monday + timedelta(days=wd), h, mi),
                               note=note if weeks_ago == 1 else ""))
    for wd, h, mi, note in maya_week:
        events.append(EventLog(activity=activity, user=maya,
                               logged_at=dt(monday + timedelta(days=wd), h, mi),
                               note=note if weeks_ago == 1 else ""))

# Current week (Mon..now=Friday): Alex 2/4 (logs the 3rd on camera), Maya 2/3.
events.append(EventLog(activity=activity, user=alex,
                       logged_at=dt(week_start, 7, 5), note=""))
events.append(EventLog(activity=activity, user=alex,
                       logged_at=dt(week_start + timedelta(days=2), 18, 35),
                       note="back and biceps 💪"))
events.append(EventLog(activity=activity, user=maya,
                       logged_at=dt(week_start + timedelta(days=1), 6, 50),
                       note="spin class, legs are jelly"))
events.append(EventLog(activity=activity, user=maya,
                       logged_at=dt(week_start + timedelta(days=3), 19, 10), note=""))

EventLog.objects.bulk_create(events)

# Reactions from the partner on this week's events.
for ev in EventLog.objects.filter(logged_at__gte=dt(week_start, 0, 0)):
    other = maya if ev.user_id == alex.id else alex
    emoji = "🔥" if ev.note else "👏"
    Reaction.objects.create(event=ev, user=other, emoji=emoji)
extra = EventLog.objects.filter(user=alex, note__icontains="biceps").first()
if extra:
    Reaction.objects.create(event=extra, user=maya, emoji="💪")

# A nudge from Maya on Thursday evening.
nudge = Nudge.objects.create(project=project, from_user=maya, to_user=alex)
Nudge.objects.filter(pk=nudge.pk).update(
    created_at=dt(week_start + timedelta(days=3), 20, 30)
)

print("Seeded demo DB at", DEMO_DB)
print("Project:", project.pk, "invite token:", project.invite_token)
print("Users: alex / maya / alexj, password:", PASSWORD)
