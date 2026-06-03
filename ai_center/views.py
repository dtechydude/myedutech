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

    # featured_prompts = (
    #     PromptLibrary.objects
    #     .filter(
    #         is_featured=True,
    #         is_active=True
    #     )[:8]
    # )

    featured_prompts = (
        PromptLibrary.objects
        .filter(
            is_featured=True,
            is_active=True
        )
        .select_related("category")
    )

    all_prompts = (
        PromptLibrary.objects
        .filter(is_active=True)
        .select_related("category")
        .order_by(
            "category__display_order",
            "title"
        )
    )

    context = {
        "categories": categories,
        "featured_tools": featured_tools,
        "featured_prompts": featured_prompts,
        "all_prompts": all_prompts,
    }

    return render(
        request,
        "ai_center/dashboard.html",
        context
    )



@login_required
def ai_usage_guide(request):
    return render(
        request,
        "ai_center/ai_guide.html"
    )