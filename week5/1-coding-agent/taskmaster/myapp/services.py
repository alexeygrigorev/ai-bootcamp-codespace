from django.db.models import Q
from .models import Task


def get_user_visible_tasks(user):
    """Return a base queryset of Tasks visible to the given user.

    This mirrors the filter used on the home page and is intended for reuse.
    The queryset is distinct to avoid duplicates when multiple relations match.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        # return empty queryset
        return Task.objects.none()

    # use related_query_name 'membership' for team lookups
    qs = Task.objects.filter(Q(owner=user) | Q(shared_with=user) | Q(team__membership__user=user)).distinct()
    return qs
