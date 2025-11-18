try:
    from django.test import TestCase
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.db import IntegrityError
    from datetime import timedelta

    from myapp.models import Team, TeamMembership, Task, TaskComment

    User = get_user_model()


    class ModelsTestCase(TestCase):
        def setUp(self):
            self.owner = User.objects.create_user(username="owner", password="pass", email="owner@example.com")
            self.shared = User.objects.create_user(username="shared", password="pass", email="shared@example.com")
            self.manager = User.objects.create_user(username="manager", password="pass", email="manager@example.com")
            self.viewer = User.objects.create_user(username="viewer", password="pass", email="viewer@example.com")

            self.team = Team.objects.create(name="Alpha", owner=self.owner)
            # memberships
            TeamMembership.objects.create(team=self.team, user=self.manager, role=TeamMembership.ROLE_MANAGER)
            TeamMembership.objects.create(team=self.team, user=self.viewer, role=TeamMembership.ROLE_VIEWER)

            # create a task
            self.task = Task.objects.create(title="Sample Task", description="Do stuff", owner=self.owner, team=self.team)
            self.task.shared_with.add(self.shared)

        def test_team_membership_unique_constraint(self):
            # attempting to create duplicate membership should raise IntegrityError
            with self.assertRaises(IntegrityError):
                TeamMembership.objects.create(team=self.team, user=self.manager, role=TeamMembership.ROLE_MEMBER)

        def test_task_permissions_can_view_and_edit(self):
            # owner can view and edit
            self.assertTrue(self.task.can_view(self.owner))
            self.assertTrue(self.task.can_edit(self.owner))

            # shared user can view and edit
            self.assertTrue(self.task.can_view(self.shared))
            self.assertTrue(self.task.can_edit(self.shared))

            # manager (team role) can view and edit
            self.assertTrue(self.task.can_view(self.manager))
            self.assertTrue(self.task.can_edit(self.manager))

            # viewer can view but cannot edit
            self.assertTrue(self.task.can_view(self.viewer))
            self.assertFalse(self.task.can_edit(self.viewer))

        def test_toggling_completion_sets_completed_at(self):
            # initially not completed
            self.assertFalse(self.task.is_completed)
            self.assertIsNone(self.task.completed_at)

            # mark completed
            self.task.is_completed = True
            self.task.save()
            self.task.refresh_from_db()
            self.assertTrue(self.task.is_completed)
            self.assertIsNotNone(self.task.completed_at)
            self.assertIsNotNone(self.task.completed_at.tzinfo)

            # uncomplete
            self.task.is_completed = False
            self.task.save()
            self.task.refresh_from_db()
            self.assertFalse(self.task.is_completed)
            self.assertIsNone(self.task.completed_at)

        def test_string_representations(self):
            self.assertIn("Alpha", str(self.team))
            membership = self.team.memberships.first()
            self.assertIn(str(membership.user.username), str(membership))
            self.assertIn("Sample Task", str(self.task))
            comment = TaskComment.objects.create(task=self.task, author=self.owner, text="Nice work")
            self.assertIn("Comment by", str(comment))

except ImportError:
    import pytest

    pytest.skip("Django not installed - skipping Django model tests", allow_module_level=True)
