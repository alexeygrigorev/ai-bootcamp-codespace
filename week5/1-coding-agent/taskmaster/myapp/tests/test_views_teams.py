try:
    from django.test import TestCase, Client
    from django.urls import reverse
    from django.contrib.auth import get_user_model

    from myapp.models import Team, TeamMembership

    User = get_user_model()


    class TeamViewsTestCase(TestCase):
        def setUp(self):
            self.client = Client()
            self.owner = User.objects.create_user(username="owner", password="pass", email="owner@example.com")
            self.manager = User.objects.create_user(username="mgr", password="pass", email="mgr@example.com")
            self.viewer = User.objects.create_user(username="viewer", password="pass", email="viewer@example.com")

        def test_create_team_sets_owner_membership(self):
            self.client.login(username="owner", password="pass")
            resp = self.client.post(reverse("team_create"), {"name": "Delta"})
            # redirect to manage
            self.assertEqual(resp.status_code, 302)
            team = Team.objects.get(name="Delta")
            self.assertEqual(team.owner, self.owner)
            self.assertTrue(team.memberships.filter(user=self.owner, role=TeamMembership.ROLE_OWNER).exists())

        def test_manager_can_add_and_remove_members(self):
            # owner creates team
            self.client.login(username="owner", password="pass")
            resp = self.client.post(reverse("team_create"), {"name": "Echo"})
            team = Team.objects.get(name="Echo")
            # make manager a manager
            TeamMembership.objects.create(team=team, user=self.manager, role=TeamMembership.ROLE_MANAGER)

            # manager adds viewer
            self.client.login(username="mgr", password="pass")
            resp = self.client.post(reverse("team_member_add", args=[team.pk]), {"username": self.viewer.username})
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(team.memberships.filter(user=self.viewer).exists())

            # manager removes viewer
            membership = team.memberships.get(user=self.viewer)
            resp = self.client.post(reverse("team_member_remove", args=[team.pk, self.viewer.pk]))
            self.assertEqual(resp.status_code, 302)
            self.assertFalse(team.memberships.filter(user=self.viewer).exists())

        def test_viewer_cannot_manage_team(self):
            # owner creates team
            self.client.login(username="owner", password="pass")
            resp = self.client.post(reverse("team_create"), {"name": "Foxtrot"})
            team = Team.objects.get(name="Foxtrot")
            # add viewer role
            TeamMembership.objects.create(team=team, user=self.viewer, role=TeamMembership.ROLE_VIEWER)
            # viewer tries to access manage page
            self.client.login(username="viewer", password="pass")
            resp = self.client.get(reverse("team_manage", args=[team.pk]))
            # should redirect to team list because not permitted
            self.assertEqual(resp.status_code, 302)

except ImportError:
    import pytest

    pytest.skip("Django not installed - skipping Django team tests", allow_module_level=True)
