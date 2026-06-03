from django.core.management.base import BaseCommand

from ai_center.models import PromptCategory


class Command(BaseCommand):

    help = "Load Prompt Categories"

    def handle(self, *args, **kwargs):

        categories = [

            "Lesson Notes",

            "CBT Questions",

            "Theory Questions",

            "Marking Schemes",

            "Assignments",

            "Timetable Generation",

            "Curriculum Planning",

            "Result Analysis",

            "Parent Communication",

            "School Administration",

        ]

        for index, name in enumerate(categories):

            PromptCategory.objects.get_or_create(

                name=name,

                defaults={

                    "slug": name.lower().replace(" ", "-"),

                    "display_order": index,

                    "is_active": True,

                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Prompt Categories Loaded Successfully."
            )
        )