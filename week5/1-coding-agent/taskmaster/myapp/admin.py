from django.contrib import admin
from django.utils.html import format_html

from . import models


class TeamMembershipInline(admin.TabularInline):
    model = models.TeamMembership
    extra = 1
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name",)
    inlines = (TeamMembershipInline,)
    raw_id_fields = ("owner",)


@admin.register(models.TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "created_at")
    list_filter = ("role", "team")
    raw_id_fields = ("team", "user")
    search_fields = ("user__username",)


@admin.register(models.Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "team", "priority", "due_date", "is_completed", "updated_at")
    list_filter = ("priority", "is_completed", "team")
    search_fields = ("title", "description")
    raw_id_fields = ("owner", "team", "shared_with")
    date_hierarchy = "due_date"
    ordering = ("-updated_at",)


@admin.register(models.TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "created_at",)
    raw_id_fields = ("task", "author")
    search_fields = ("text",)
