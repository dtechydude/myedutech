from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import (
    AIToolCategory,
    AITool,
)

from .models import PromptLibrary


@login_required
def ai_center_dashboard(request):

    categories = (
        AIToolCategory.objects
        .prefetch_related('tools')
        .all()
    )

    featured_tools = (
        AITool.objects
        .filter(
            is_featured=True,
            is_active=True
        )[:4]
    )

    featured_prompts = (
        PromptLibrary.objects
        .filter(
            is_featured=True,
            is_active=True
        )[:8]
    )

    context = {
        "categories": categories,
        "featured_tools": featured_tools,
        "featured_prompts": featured_prompts,
    }

    return render(
        request,
        "ai_center/dashboard.html",
        context
    )