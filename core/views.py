from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Project


@login_required
def home(request):
    projects = (
        Project.objects.filter(members=request.user)
        .prefetch_related("activities")
        .order_by("name")
    )
    return render(request, "core/home.html", {"projects": projects})
