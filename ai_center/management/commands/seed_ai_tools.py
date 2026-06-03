from django.core.management.base import BaseCommand

from ai_center.models import (
    AIToolCategory,
    AITool
)


class Command(BaseCommand):

    help = "Load AI Tools Seed Data"

    def handle(self, *args, **kwargs):

        categories = {

            "General AI": "fas fa-robot",

            "Education AI": "fas fa-graduation-cap",

            "Research & Curriculum": "fas fa-book",

            "Presentation & Content Creation": "fas fa-chalkboard",

            "Assessment & CBT": "fas fa-clipboard-check",

            "Visual Learning": "fas fa-project-diagram",

            "Video & Media Creation": "fas fa-video",

        }

        for name, icon in categories.items():

            AIToolCategory.objects.get_or_create(
                name=name,
                defaults={
                    "icon": icon
                }
            )

        tools = [

            {
                "category": "General AI",
                "name": "ChatGPT",
                "description": "Generate lesson notes, CBT, examinations and school documents.",
                "best_for": "Lesson Notes, CBT, Exams",
                "website_url": "https://chatgpt.com",
                "icon_class": "fas fa-comments",
                "is_featured": True,
            },

            {
                "category": "General AI",
                "name": "Gemini",
                "description": "Google AI assistant.",
                "best_for": "Research, Curriculum",
                "website_url": "https://gemini.google.com",
                "icon_class": "fab fa-google",
                "is_featured": True,
            },

            {
                "category": "Education AI",
                "name": "NotebookLM",
                "description": "Google AI study assistant.",
                "best_for": "Research, Study Materials",
                "website_url": "https://notebooklm.google.com",
                "icon_class": "fas fa-book-open",
                "is_featured": True,
            },

            {
                "category": "Education AI",
                "name": "MagicSchool AI",
                "description": "AI built for teachers.",
                "best_for": "Lesson Planning",
                "website_url": "https://www.magicschool.ai",
                "icon_class": "fas fa-school",
            },

            {
                "category": "Education AI",
                "name": "Eduaide AI",
                "description": "Teacher productivity tool.",
                "best_for": "Teaching Resources",
                "website_url": "https://www.eduaide.ai",
                "icon_class": "fas fa-chalkboard-teacher",
            },

            {
                "category": "Research & Curriculum",
                "name": "Perplexity",
                "description": "AI-powered research assistant.",
                "best_for": "Research",
                "website_url": "https://www.perplexity.ai",
                "icon_class": "fas fa-search",
                "is_featured": True,
            },

            {
                "category": "Research & Curriculum",
                "name": "Claude",
                "description": "Long-form educational content generation.",
                "best_for": "Lesson Notes",
                "website_url": "https://claude.ai",
                "icon_class": "fas fa-brain",
            },

            {
                "category": "Presentation & Content Creation",
                "name": "Canva AI",
                "description": "Presentation and graphics generation.",
                "best_for": "Presentations",
                "website_url": "https://www.canva.com",
                "icon_class": "fas fa-palette",
            },

            {
                "category": "Presentation & Content Creation",
                "name": "Gamma",
                "description": "AI slide creator.",
                "best_for": "Slides",
                "website_url": "https://gamma.app",
                "icon_class": "fas fa-desktop",
            },

            {
                "category": "Assessment & CBT",
                "name": "Quizizz",
                "description": "Interactive classroom quizzes.",
                "best_for": "CBT",
                "website_url": "https://quizizz.com",
                "icon_class": "fas fa-question-circle",
            },

            {
                "category": "Assessment & CBT",
                "name": "Kahoot",
                "description": "Gamified assessments.",
                "best_for": "Quizzes",
                "website_url": "https://kahoot.com",
                "icon_class": "fas fa-gamepad",
            },

            {
                "category": "Assessment & CBT",
                "name": "Quizlet",
                "description": "Flashcards and revision.",
                "best_for": "Revision",
                "website_url": "https://quizlet.com",
                "icon_class": "fas fa-clone",
            },

            {
                "category": "Visual Learning",
                "name": "Miro",
                "description": "Collaborative whiteboard.",
                "best_for": "Brainstorming",
                "website_url": "https://miro.com",
                "icon_class": "fas fa-project-diagram",
            },

            {
                "category": "Visual Learning",
                "name": "MindMeister",
                "description": "Mind mapping.",
                "best_for": "Lesson Planning",
                "website_url": "https://www.mindmeister.com",
                "icon_class": "fas fa-sitemap",
            },

            {
                "category": "Visual Learning",
                "name": "Napkin AI",
                "description": "Visual explanation generator.",
                "best_for": "Visual Learning",
                "website_url": "https://napkin.ai",
                "icon_class": "fas fa-lightbulb",
            },

            {
                "category": "Video & Media Creation",
                "name": "HeyGen",
                "description": "AI video creation.",
                "best_for": "Educational Videos",
                "website_url": "https://www.heygen.com",
                "icon_class": "fas fa-video",
            },

            {
                "category": "Video & Media Creation",
                "name": "Synthesia",
                "description": "AI training videos.",
                "best_for": "Staff Training",
                "website_url": "https://www.synthesia.io",
                "icon_class": "fas fa-film",
            },

        ]

        for item in tools:

            category = AIToolCategory.objects.get(
                name=item["category"]
            )

            AITool.objects.get_or_create(

                name=item["name"],

                defaults={

                    "category": category,

                    "description": item["description"],

                    "best_for": item["best_for"],

                    "website_url": item["website_url"],

                    "icon_class": item["icon_class"],

                    "is_featured": item.get(
                        "is_featured",
                        False
                    ),

                    "is_active": True,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "AI Tools loaded successfully."
            )
        )