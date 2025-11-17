try:
    from django.test import TestCase, override_settings
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.core import mail
    from django.core.management import call_command
    from io import StringIO
    from datetime import timedelta

    from myapp.models import Task

    User = get_user_model()


    class ManagementCommandTestCase(TestCase):
        @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='no-reply@example.com')
        def test_send_deadline_reminders_sends_emails_and_prints_summary(self):
            now = timezone.now()
            u1 = User.objects.create_user(username="one", password="pass", email="one@example.com")
            u2 = User.objects.create_user(username="two", password="pass", email="two@example.com")
            # tasks due within next 24h
            Task.objects.create(title="Soon1", owner=u1, due_date=now + timedelta(hours=2))
            Task.objects.create(title="Soon2", owner=u1, due_date=now + timedelta(hours=20))
            # task for other user
            Task.objects.create(title="Soon3", owner=u2, due_date=now + timedelta(hours=3))

            out = StringIO()
            call_command("send_deadline_reminders", stdout=out)
            output = out.getvalue()
            # should mention sent lines and summary
            self.assertIn("Sent", output)
            self.assertIn("Summary", output)

            # check emails captured
            self.assertEqual(len(mail.outbox), 2)
            subjects = [m.subject for m in mail.outbox]
            self.assertTrue(any("You have" in s for s in subjects))

except ImportError:
    import pytest

    pytest.skip("Django not installed - skipping management command tests", allow_module_level=True)
