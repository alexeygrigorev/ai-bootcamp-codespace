try:
    from django.test import TestCase, Client
    from django.urls import reverse
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from myapp.models import Task, Team, TeamMembership, TaskComment

    User = get_user_model()


    class CommentViewsTestCase(TestCase):
        def setUp(self):
            self.client = Client()
            self.owner = User.objects.create_user(username="owner", password="pass", email="owner@example.com")
            self.other = User.objects.create_user(username="other", password="pass", email="other@example.com")
            self.team = Team.objects.create(name="Gamma", owner=self.owner)
            TeamMembership.objects.create(team=self.team, user=self.other, role=TeamMembership.ROLE_VIEWER)
            self.task = Task.objects.create(title="WithComments", owner=self.owner, team=self.team)

        def test_post_comment_and_appear_on_detail(self):
            self.client.login(username="other", password="pass")
            resp = self.client.post(reverse("task_comment_add", args=[self.task.pk]), {"text": "Hello"})
            # should redirect to detail
            self.assertEqual(resp.status_code, 302)
            detail = self.client.get(reverse("task_detail", args=[self.task.pk]))
            self.assertContains(detail, "Hello")
            self.assertTrue(TaskComment.objects.filter(task=self.task, text__icontains="Hello").exists())

        def test_unauthorized_cannot_comment(self):
            # create stranger not member and not shared
            stranger = User.objects.create_user(username="stranger", password="pass")
            self.client.login(username="stranger", password="pass")
            resp = self.client.post(reverse("task_comment_add", args=[self.task.pk]), {"text": "Nope"})
            self.assertEqual(resp.status_code, 403)

except ImportError:
    import pytest

    pytest.skip("Django not installed - skipping Django comment tests", allow_module_level=True)
