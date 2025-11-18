from django.conf import settings
from django.db import models
from django.utils import timezone


class Team(models.Model):
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_teams",
        related_query_name="owned_team",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_owner_team_name")
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    ROLE_OWNER = "OWNER"
    ROLE_MANAGER = "MANAGER"
    ROLE_MEMBER = "MEMBER"
    ROLE_VIEWER = "VIEWER"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_MEMBER, "Member"),
        (ROLE_VIEWER, "Viewer"),
    ]

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
        related_query_name="membership",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        related_query_name="team_membership",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_user_membership")
        ]
        indexes = [
            models.Index(fields=["team", "user"], name="idx_team_user"),
        ]

    def __str__(self):
        return f"{self.user} in {self.team} as {self.role}"


class Task(models.Model):
    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_tasks",
        related_query_name="owned_task",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tasks",
        related_query_name="task",
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    due_date = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="shared_tasks", related_query_name="shared_task"
    )

    class Meta:
        indexes = [
            models.Index(fields=["owner", "is_completed"], name="idx_owner_completed"),
            models.Index(fields=["due_date"], name="idx_due_date"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} (owner={self.owner})"

    def can_view(self, user):
        if user is None or not user.is_authenticated:
            return False
        if user == self.owner:
            return True
        if self.shared_with.filter(pk=user.pk).exists():
            return True
        if self.team and self.team.memberships.filter(user=user).exists():
            return True
        return False

    def can_edit(self, user):
        if user is None or not user.is_authenticated:
            return False
        if user == self.owner:
            return True
        if self.shared_with.filter(pk=user.pk).exists():
            return True
        # check team membership and role
        if self.team:
            membership = self.team.memberships.filter(user=user).first()
            if membership and membership.role in {TeamMembership.ROLE_OWNER, TeamMembership.ROLE_MANAGER, TeamMembership.ROLE_MEMBER}:
                return True
        return False

    def save(self, *args, **kwargs):
        # set or clear completed_at based on is_completed transitions
        if self.pk:
            try:
                prev = Task.objects.get(pk=self.pk)
            except Task.DoesNotExist:
                prev = None
        else:
            prev = None

        if self.is_completed:
            if not self.completed_at:
                # if previously not completed, set timestamp
                if not prev or not prev.is_completed:
                    self.completed_at = timezone.now()
        else:
            # if now marked not completed, clear completed_at
            self.completed_at = None

        super().save(*args, **kwargs)


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments", related_query_name="comment")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"
