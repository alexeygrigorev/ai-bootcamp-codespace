from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q, F, Case, When, IntegerField, Value, OrderBy
from django.utils import timezone
from datetime import timedelta

from .models import Task, TaskComment, Team, TeamMembership
from .forms import (
    TaskForm,
    TaskQuickForm,
    TaskCommentForm,
    TeamForm,
    TeamMemberAddForm,
)
from .permissions import user_can_view_task, user_can_edit_task, is_team_manager_or_owner
from .services import get_user_visible_tasks

from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm


@login_required
def home(request):
    user = request.user
    qs = get_user_visible_tasks(user)

    # apply filters from GET
    status = request.GET.get("status", "all")
    priority = request.GET.get("priority")
    team_id = request.GET.get("team")
    q = request.GET.get("q")
    due = request.GET.get("due")

    if status == "open":
        qs = qs.filter(is_completed=False)
    elif status == "done":
        qs = qs.filter(is_completed=True)

    if priority in ("low", "medium", "high"):
        mapping = {"low": Task.PRIORITY_LOW, "medium": Task.PRIORITY_MEDIUM, "high": Task.PRIORITY_HIGH}
        qs = qs.filter(priority=mapping[priority])

    if team_id:
        try:
            tid = int(team_id)
            qs = qs.filter(team_id=tid)
        except (ValueError, TypeError):
            pass

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    now = timezone.now()
    if due == "today":
        qs = qs.filter(due_date__date=now.date())
    elif due == "7days":
        qs = qs.filter(due_date__gte=now, due_date__lte=now + timedelta(days=7))
    elif due == "overdue":
        qs = qs.filter(due_date__lt=now, is_completed=False)

    # annotate priority rank for ordering
    qs = qs.annotate(
        priority_rank=Case(
            When(priority=Task.PRIORITY_HIGH, then=Value(3)),
            When(priority=Task.PRIORITY_MEDIUM, then=Value(2)),
            When(priority=Task.PRIORITY_LOW, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )

    # order: is_completed asc, due_date asc nulls last, priority desc, updated_at desc
    qs = qs.order_by(
        "is_completed",
        OrderBy(F("due_date"), nulls_last=True),
        "-priority_rank",
        "-updated_at",
    )

    quick_form = TaskQuickForm()

    # teams the user belongs to (for filters)
    teams = Team.objects.filter(Q(owner=user) | Q(membership__user=user)).distinct()

    # simple reminders: upcoming due tasks (today + next 24h) that are not completed
    reminders = (
        qs.filter(is_completed=False)
        .filter(due_date__isnull=False)
        .filter(due_date__gte=now, due_date__lte=now + timedelta(days=1))
        .order_by("due_date")[:5]
    )

    filters = {"status": status, "priority": priority, "team": team_id, "q": q, "due": due}

    context = {"tasks": qs, "filters": filters, "quick_form": quick_form, "teams": teams, "reminders": reminders}
    return render(request, "home.html", context)


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.save()
            # save m2m
            form.save_m2m()
            messages.success(request, "Task created successfully. \u2705")
            return redirect(reverse("home"))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TaskForm(user=request.user)
    return render(request, "myapp/task_form.html", {"form": form})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_edit_task(request.user, task):
        return HttpResponseForbidden("You do not have permission to edit this task.")

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully. \u2728")
            return redirect(reverse("task_detail", args=[task.pk]))
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = TaskForm(instance=task, user=request.user)
    return render(request, "myapp/task_form.html", {"form": form, "task": task})


@require_POST
@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_edit_task(request.user, task):
        return HttpResponseForbidden("You do not have permission to delete this task.")
    task.delete()
    messages.success(request, "Task deleted. \ud83d\uddd1\ufe0f")
    return redirect(reverse("home"))


@require_POST
@login_required
def task_toggle_complete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_edit_task(request.user, task):
        return HttpResponseForbidden("You do not have permission to change this task.")
    task.is_completed = not task.is_completed
    # Task.save will handle completed_at
    task.save()
    messages.success(request, "Task status updated.")
    # redirect back preserving query params if possible
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)
    return redirect(reverse("home"))


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_view_task(request.user, task):
        return HttpResponseForbidden("You do not have permission to view this task.")
    comments = task.comments.order_by("-created_at")
    comment_form = TaskCommentForm()
    return render(request, "myapp/task_detail.html", {"task": task, "comments": comments, "comment_form": comment_form})


@require_POST
@login_required
def task_comment_add(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_view_task(request.user, task):
        return HttpResponseForbidden("You do not have permission to comment on this task.")
    form = TaskCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.author = request.user
        comment.save()
        messages.success(request, "Comment added. \ud83d\udcac")
    else:
        messages.error(request, "Could not add comment. Please fix errors.")
    return redirect(reverse("task_detail", args=[task.pk]))


@login_required
def team_list(request):
    user = request.user
    teams = Team.objects.filter(Q(owner=user) | Q(membership__user=user)).distinct()
    return render(request, "myapp/team_list.html", {"teams": teams})


@login_required
def team_create(request):
    if request.method == "POST":
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.owner = request.user
            team.save()
            # create membership for owner
            TeamMembership.objects.create(team=team, user=request.user, role=TeamMembership.ROLE_OWNER)
            messages.success(request, "Team created.")
            return redirect(reverse("team_manage", args=[team.pk]))
        else:
            messages.error(request, "Please correct errors below.")
    else:
        form = TeamForm()
    return render(request, "myapp/team_form.html", {"form": form})


@login_required
def team_manage(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    if not is_team_manager_or_owner(request.user, team):
        # use friendly message+redirect for team management access denied
        messages.error(request, "You do not have permission to manage this team.")
        return redirect(reverse("teams"))
    members = list(team.memberships.select_related("user"))
    add_form = TeamMemberAddForm(team=team)
    return render(request, "myapp/team_manage.html", {"team": team, "members": members, "add_form": add_form})


@require_POST
@login_required
def team_member_add(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    if not is_team_manager_or_owner(request.user, team):
        messages.error(request, "You do not have permission to add members to this team.")
        return redirect(reverse("teams"))
    form = TeamMemberAddForm(request.POST, team=team)
    if form.is_valid():
        user = form.get_user()
        TeamMembership.objects.create(team=team, user=user, role=TeamMembership.ROLE_MEMBER)
        messages.success(request, f"Added {user.username} to the team. \ud83d\udc65")
    else:
        messages.error(request, "Could not add member. Please fix errors.")
    return redirect(reverse("team_manage", args=[team.pk]))


@require_POST
@login_required
def team_member_remove(request, team_id, user_id):
    team = get_object_or_404(Team, pk=team_id)
    if not is_team_manager_or_owner(request.user, team):
        messages.error(request, "You do not have permission to remove members from this team.")
        return redirect(reverse("teams"))
    # prevent removing owner
    if team.owner_id == user_id:
        messages.error(request, "Cannot remove the team owner.")
        return redirect(reverse("team_manage", args=[team.pk]))
    membership = team.memberships.filter(user_id=user_id).first()
    if membership:
        membership.delete()
        # remove user from shared_with for tasks in this team
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            tasks = Task.objects.filter(team=team, shared_with=user)
            for t in tasks:
                t.shared_with.remove(user)
        except User.DoesNotExist:
            pass
        messages.success(request, "Member removed from team.")
    else:
        messages.error(request, "Membership not found.")
    return redirect(reverse("team_manage", args=[team.pk]))


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # log in
            raw_pw = form.cleaned_data.get("password1")
            auth_user = authenticate(username=user.username, password=raw_pw)
            if auth_user:
                login(request, auth_user)
            messages.success(request, "Welcome! Your account has been created. \ud83c\udf89")
            return redirect(reverse("home"))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
