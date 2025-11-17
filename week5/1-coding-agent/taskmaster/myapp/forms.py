from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Task, TaskComment, Team

User = get_user_model()


class TaskForm(forms.ModelForm):
    """Form for creating/editing tasks.

    Accepts an optional `user` kwarg in __init__ to limit team choices to teams
    the user belongs to and to use as the implicit owner when validating team membership.
    """

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date", "team", "shared_with"]
        widgets = {
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # pop user from kwargs if provided
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # limit shared_with to active users only
        self.fields["shared_with"].queryset = User.objects.filter(is_active=True)

        # if a user was provided, limit team choices to teams the user belongs to
        if self.user is not None:
            # teams where the user is a member
            # use related_query_name ("membership") for lookups
            self.fields["team"].queryset = Team.objects.filter(membership__user=self.user).distinct()

        # container for non-blocking warnings (e.g., due_date in the past)
        self.warnings = []

    def clean(self):
        cleaned = super().clean()
        due_date = cleaned.get("due_date")

        # non-blocking warning if due_date is in the past
        if due_date is not None:
            # compare with timezone-aware now
            now = timezone.now()
            if due_date < now:
                # append a warning; do not raise ValidationError so form can still validate
                self.warnings.append("Due date/time is in the past. This is allowed for testing but you may want to set a future date.")

        # Validate team membership for owner: if a team is selected, ensure the task owner is a member of that team
        team = cleaned.get("team")
        if team:
            # determine owner candidate: instance.owner if set, else user passed into form
            owner = getattr(self.instance, "owner", None) or self.user
            if owner is None:
                # cannot fully validate without an owner; skip strict enforcement
                return cleaned

            # check membership: either owner is the team.owner or has membership
            if not (team.owner_id == owner.id or team.memberships.filter(user=owner).exists()):
                # raise a ValidationError to block saving if owner is not a member
                raise forms.ValidationError("Selected team requires that the task owner is a member of that team.")

        return cleaned


class TaskQuickForm(forms.ModelForm):
    """Quick task creation form with minimal fields."""

    class Meta:
        model = Task
        fields = ["title", "priority", "due_date"]
        widgets = {"due_date": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warnings = []

    def clean(self):
        cleaned = super().clean()
        due_date = cleaned.get("due_date")
        if due_date is not None and due_date < timezone.now():
            self.warnings.append("Due date/time is in the past. This is allowed for testing but you may want to set a future date.")
        return cleaned


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name"]


class TeamMemberAddForm(forms.Form):
    username = forms.CharField(max_length=150)

    def __init__(self, *args, **kwargs):
        # accept an optional `team` kwarg to check membership against
        self.team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        self._user_obj = None

    def clean_username(self):
        username = self.cleaned_data.get("username")
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username was found.")
        self._user_obj = user
        return username

    def clean(self):
        cleaned = super().clean()
        if self.team and self._user_obj:
            # check if user is already member
            if self.team.memberships.filter(user=self._user_obj).exists() or self.team.owner_id == self._user_obj.id:
                raise forms.ValidationError("This user is already a member of the team.")
        return cleaned

    def get_user(self):
        return self._user_obj
