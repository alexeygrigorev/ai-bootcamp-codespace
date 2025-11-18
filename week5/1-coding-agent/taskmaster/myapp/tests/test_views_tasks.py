try:
    from django.test import TestCase, Client
    from django.urls import reverse
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from datetime import timedelta

    from myapp.models import Task, Team, TeamMembership

    User = get_user_model()


    class TaskViewsTestCase(TestCase):
        def setUp(self):
            self.client = Client()
            self.user = User.objects.create_user(username="alice", password="pass", email="alice@example.com")
            self.other = User.objects.create_user(username="bob", password="pass", email="bob@example.com")
            self.team = Team.objects.create(name="Beta", owner=self.user)
            TeamMembership.objects.create(team=self.team, user=self.user, role=TeamMembership.ROLE_OWNER)

        def test_home_requires_login(self):
            resp = self.client.get(reverse("home"))
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse("login"), resp.url)

        def test_create_task_and_show_on_home(self):
            self.client.login(username="alice", password="pass")
            due = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
            resp = self.client.post(reverse("task_create"), {"title": "New Task", "description": "Do it", "priority": "MEDIUM", "due_date": due, "team": self.team.pk})
            # should redirect to home
            self.assertEqual(resp.status_code, 302)
            home = self.client.get(reverse("home"))
            self.assertContains(home, "New Task")

        def test_filters_status_priority_and_search(self):
            self.client.login(username="alice", password="pass")
            t1 = Task.objects.create(title="Open High", owner=self.user, priority=Task.PRIORITY_HIGH)
            t2 = Task.objects.create(title="Done Low", owner=self.user, priority=Task.PRIORITY_LOW, is_completed=True)
            # status=open
            resp = self.client.get(reverse("home") + "?status=open")
            self.assertContains(resp, "Open High")
            self.assertNotContains(resp, "Done Low")
            # priority filter
            resp = self.client.get(reverse("home") + "?priority=high")
            self.assertContains(resp, "Open High")
            self.assertNotContains(resp, "Done Low")
            # search
            resp = self.client.get(reverse("home") + "?q=Done")
            self.assertContains(resp, "Done Low")

        def test_toggle_complete_updates_state(self):
            self.client.login(username="alice", password="pass")
            t = Task.objects.create(title="Toggle", owner=self.user)
            self.assertFalse(t.is_completed)
            resp = self.client.post(reverse("task_toggle_complete", args=[t.pk]))
            self.assertIn(resp.status_code, (302, 200))
            t.refresh_from_db()
            self.assertTrue(t.is_completed)

        def test_edit_forbidden_for_non_permitted(self):
            # create task owned by alice
            t = Task.objects.create(title="Private", owner=self.user)
            # bob tries to edit
            self.client.login(username="bob", password="pass")
            resp = self.client.post(reverse("task_edit", args=[t.pk]), {"title": "Hacked", "priority": "MEDIUM"})
            self.assertEqual(resp.status_code, 403)

        def test_delete_only_by_editor(self):
            # create task and share with bob
            t = Task.objects.create(title="ToDelete", owner=self.user)
            t.shared_with.add(self.other)
            # bob deletes (shared user can edit/delete per Task.can_edit)
            self.client.login(username="bob", password="pass")
            resp = self.client.post(reverse("task_delete", args=[t.pk]))
            self.assertEqual(resp.status_code, 302)
            self.assertFalse(Task.objects.filter(pk=t.pk).exists())

            # recreate and ensure non-authorized cannot delete
            t2 = Task.objects.create(title="NoDelete", owner=self.user)
            # create a random user not shared
            stranger = User.objects.create_user(username="stranger", password="pass")
            self.client.login(username="stranger", password="pass")
            resp = self.client.post(reverse("task_delete", args=[t2.pk]))
            self.assertEqual(resp.status_code, 403)
            self.assertTrue(Task.objects.filter(pk=t2.pk).exists())

except ImportError:
    import pytest

    pytest.skip("Django not installed - skipping Django view tests", allow_module_level=True)
