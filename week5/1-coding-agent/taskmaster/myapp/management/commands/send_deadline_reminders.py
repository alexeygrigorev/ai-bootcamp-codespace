from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from datetime import timedelta

from myapp.models import Task


class Command(BaseCommand):
    help = "Send email reminders for tasks due within the next 24 hours (or overdue within past day)."

    def handle(self, *args, **options):
        now = timezone.now()
        window_end = now + timedelta(hours=24)
        window_start_overdue = now - timedelta(hours=24)

        # select tasks not completed with a due date in next 24h or overdue within past day
        tasks_qs = (
            Task.objects.filter(is_completed=False, due_date__isnull=False)
            .filter(
                models.Q(due_date__gte=now, due_date__lte=window_end)
                | models.Q(due_date__gte=window_start_overdue, due_date__lt=now)
            )
            .select_related("owner", "team")
            .prefetch_related("shared_with", "team__memberships")
        )

        # Build mapping of user pk -> {user, email, tasks}
        tasks_per_user = {}

        for task in tasks_qs:
            recipients = set()
            if task.owner:
                recipients.add(task.owner)

            for u in task.shared_with.all():
                recipients.add(u)

            if task.team:
                # include all team members
                memberships = task.team.memberships.select_related("user").all()
                for m in memberships:
                    if m.user:
                        recipients.add(m.user)

            for user in recipients:
                # skip inactive users
                if not getattr(user, "is_active", True):
                    continue

                user_entry = tasks_per_user.setdefault(user.pk, {"user": user, "email": getattr(user, "email", None), "tasks": []})
                user_entry["tasks"].append(task)

        # Send one email per recipient and print a summary
        total_sent = 0
        for uid, info in tasks_per_user.items():
            user = info["user"]
            recipient_email = info["email"]
            tasks = sorted(info["tasks"], key=lambda t: t.due_date or timezone.datetime.max.replace(tzinfo=timezone.utc))

            if not recipient_email:
                self.stdout.write(self.style.WARNING(f"Skipping {user} (no email); would have {len(tasks)} reminders"))
                continue

            subject = f"⏰ You have {len(tasks)} task(s) due soon"
            lines = [f"Hi {user.get_full_name() or user.username},", "", "Here are the tasks that are due within the next 24 hours (or overdue within the past day):", ""]

            for t in tasks:
                due_local = timezone.localtime(t.due_date).strftime("%Y-%m-%d %H:%M %Z") if t.due_date else "No due date"
                team_label = f" [Team: {t.team.name}]" if t.team else ""
                lines.append(f"- {t.title}{team_label} — due: {due_local}")

            lines.append("")
            lines.append("Visit your dashboard to manage these tasks.")
            message = "\n".join(lines)

            # Use configured email backend (console in development)
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient_email])
            total_sent += 1
            self.stdout.write(self.style.SUCCESS(f"Sent {len(tasks)} reminders to {user} <{recipient_email}>") )

        # summary
        self.stdout.write(self.style.SUCCESS(f"Summary: {len(tasks_per_user)} recipient(s) processed, {total_sent} email(s) sent."))
