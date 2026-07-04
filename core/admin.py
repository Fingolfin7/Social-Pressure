from django.contrib import admin

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


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "end_date", "invite_token", "created_at")
    search_fields = ("name", "description", "created_by__username", "created_by__email")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "unit", "cadence", "created_at")
    list_filter = ("cadence",)
    search_fields = ("name", "project__name", "unit")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "joined_at")
    search_fields = ("user__username", "user__email", "project__name")


@admin.register(MemberTarget)
class MemberTargetAdmin(admin.ModelAdmin):
    list_display = ("membership", "activity", "target", "created_at")
    search_fields = ("membership__user__username", "activity__name", "activity__project__name")


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("user", "activity", "logged_at", "note", "created_at")
    list_filter = ("activity__cadence",)
    search_fields = ("user__username", "activity__name", "note")


@admin.register(Nudge)
class NudgeAdmin(admin.ModelAdmin):
    list_display = ("project", "from_user", "to_user", "created_at")
    search_fields = ("project__name", "from_user__username", "to_user__username")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "emoji", "created_at")
    search_fields = ("user__username", "emoji", "event__activity__name")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "short_endpoint", "user_agent", "created_at")
    search_fields = ("user__username", "user__email", "endpoint", "user_agent")

    @admin.display(description="Endpoint")
    def short_endpoint(self, obj):
        return obj.endpoint[:80]
