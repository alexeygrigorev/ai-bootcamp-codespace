from typing import Any

from .models import Team, Task


def user_can_view_task(user, task: Task) -> bool:
    """Delegate to Task.can_view for clarity and centralizing permission checks."""
    if task is None:
        return False
    return task.can_view(user)


def user_can_edit_task(user, task: Task) -> bool:
    """Delegate to Task.can_edit for clarity and centralizing permission checks."""
    if task is None:
        return False
    return task.can_edit(user)


def is_team_manager_or_owner(user, team: Team) -> bool:
    """Return True if the user is the team owner or has a manager role.

    This central helper allows views to consistently apply the same role checks.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if team is None:
        return False
    if team.owner_id == getattr(user, "id", None):
        return True
    membership = team.memberships.filter(user=user).first()
    if membership and membership.role in {"OWNER", "MANAGER"}:
        return True
    return False
