from django.core.management.base import BaseCommand

from ai_center.models import (
    PromptCategory,
    PromptLibrary
)
from django.utils.text import slugify


class Command(BaseCommand):

    help = "Load Educational Prompt Library"

    def handle(self, *args, **kwargs):

        prompts = [

            # LESSON NOTES

            {
                "category": "Lesson Notes",
                "title": "Generate Weekly Lesson Note",
                "school_level": "SECONDARY",
                "subject": "Any Subject",
                "prompt_text": """
Act as an experienced teacher.

Generate a complete lesson note for:

Subject: [SUBJECT]
Class: [CLASS]
Topic: [TOPIC]

Include:

1. Behavioural Objectives
2. Previous Knowledge
3. Instructional Materials
4. Introduction
5. Presentation Steps
6. Evaluation
7. Assignment
8. Reference
"""
            },

            {
                "category": "Lesson Notes",
                "title": "Generate Scheme-Based Lesson Plan",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Act as a professional teacher.

Generate a lesson plan aligned with the national curriculum.

Topic: [TOPIC]
Class: [CLASS]

Output in table format.
"""
            },

            # CBT

            {
                "category": "CBT Questions",
                "title": "Generate 40 CBT Questions",
                "school_level": "SECONDARY",
                "subject": "Any",
                "prompt_text": """
Act as a WAEC examiner.

Generate 40 CBT questions.

Subject: [SUBJECT]
Class: [CLASS]
Topic: [TOPIC]

Requirements:

- Four options A-D
- Correct answer
- Explanation
"""
            },

            {
                "category": "CBT Questions",
                "title": "Generate Objective Test",
                "school_level": "PRIMARY",
                "subject": "",
                "prompt_text": """
Generate 20 multiple-choice questions.

Class: [CLASS]

Topic: [TOPIC]

Provide answers at the end.
"""
            },

            # THEORY

            {
                "category": "Theory Questions",
                "title": "Generate Theory Examination",
                "school_level": "SECONDARY",
                "subject": "",
                "prompt_text": """
Generate a theory examination paper.

Subject: [SUBJECT]

Class: [CLASS]

Section A:
Short Answer

Section B:
Essay Questions

Include marking guide.
"""
            },

            {
                "category": "Theory Questions",
                "title": "Generate WAEC Style Questions",
                "school_level": "SECONDARY",
                "subject": "",
                "prompt_text": """
Generate WAEC-standard theory questions.

Subject: [SUBJECT]

Topic: [TOPIC]

Include examiner expectations.
"""
            },

            # MARKING SCHEME

            {
                "category": "Marking Schemes",
                "title": "Generate Marking Scheme",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate a complete marking scheme.

Subject: [SUBJECT]

Questions:

[PASTE QUESTIONS]

Allocate marks appropriately.
"""
            },

            {
                "category": "Marking Schemes",
                "title": "Generate Rubric",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Create a grading rubric.

Assessment Type:

[ASSESSMENT]

Criteria:
Knowledge
Presentation
Accuracy
Creativity

Output in table format.
"""
            },

            # ASSIGNMENT

            {
                "category": "Assignments",
                "title": "Generate Assignment",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate take-home assignment.

Subject:

[SUBJECT]

Class:

[CLASS]

Topic:

[TOPIC]

Difficulty:
Medium
"""
            },

            {
                "category": "Assignments",
                "title": "Generate Project Work",
                "school_level": "SECONDARY",
                "subject": "",
                "prompt_text": """
Generate project-based learning activity.

Subject:

[SUBJECT]

Class:

[CLASS]

Include:

Objectives
Tasks
Assessment Method
"""
            },

            # TIMETABLE

            {
                "category": "Timetable Generation",
                "title": "Generate School Timetable",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Create a weekly timetable.

School Level:

[LEVEL]

Subjects:

[SUBJECTS]

School Hours:

[HOURS]

Output in table format.
"""
            },

            {
                "category": "Timetable Generation",
                "title": "Teacher Timetable",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate timetable for teacher.

Teacher Name:

[NAME]

Subjects:

[SUBJECTS]

Classes:

[CLASSES]

Avoid clashes.
"""
            },

            # CURRICULUM

            {
                "category": "Curriculum Planning",
                "title": "Generate Scheme of Work",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate a termly scheme of work.

Subject:

[SUBJECT]

Class:

[CLASS]

Weeks:

12

Output in table format.
"""
            },

            # RESULT ANALYSIS

            {
                "category": "Result Analysis",
                "title": "Student Result Analysis",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Analyze student performance.

Provide:

Strengths
Weaknesses
Recommendations

Data:

[PASTE RESULT DATA]
"""
            },

            {
                "category": "Result Analysis",
                "title": "Class Performance Report",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate class performance report.

Subject:

[SUBJECT]

Result Data:

[PASTE SCORES]

Provide charts recommendation.
"""
            },

            # PARENT COMMUNICATION

            {
                "category": "Parent Communication",
                "title": "Parent Meeting Invitation",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Draft professional parent invitation letter.

Purpose:

[PURPOSE]

Meeting Date:

[DATE]
"""
            },

            {
                "category": "Parent Communication",
                "title": "Student Behaviour Report",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate student behaviour report.

Student Name:

[NAME]

Behaviour Observed:

[DETAILS]

Professional and constructive tone.
"""
            },

            # ADMINISTRATION

            {
                "category": "School Administration",
                "title": "School Circular",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Draft an official school circular.

Topic:

[TOPIC]

Target Audience:

[STAFF/PARENTS/STUDENTS]
"""
            },

            {
                "category": "School Administration",
                "title": "Staff Memo",
                "school_level": "GENERAL",
                "subject": "",
                "prompt_text": """
Generate staff memo.

Purpose:

[PURPOSE]

Professional tone.
"""
            },



{
    "category": "Report Card Comments",
    "title": "Generate Teacher Remarks",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Act as an experienced school teacher.

Generate professional report card remarks.

Student Average:
[AVERAGE]

Behaviour:
[BEHAVIOUR]

Attendance:
[ATTENDANCE]

Provide:

Teacher Comment
Strengths
Areas for Improvement
"""
},


{
    "category": "Report Card Comments",
    "title": "Generate Principal Remark",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Act as a school principal.

Generate a professional principal's remark.

Average Score:
[AVERAGE]

Position:
[POSITION]

Conduct:
[CONDUCT]
"""
},


{
    "category": "Psychomotor Assessment",
    "title": "Generate Psychomotor Assessment",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Assess student psychomotor skills.

Student Name:
[NAME]

Provide ratings and comments for:

Handwriting
Sports
Practical Skills
Creativity
Coordination
"""
},


{
    "category": "Affective Assessment",
    "title": "Generate Affective Domain Report",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Evaluate student affective traits.

Provide ratings and comments for:

Punctuality
Honesty
Leadership
Neatness
Obedience
Respect
Teamwork
"""
},


{
    "category": "Scheme of Work",
    "title": "Generate Termly Scheme of Work",
    "school_level": "SECONDARY",
    "subject": "",
    "prompt_text": """
Generate a complete 12-week scheme of work.

Subject:
[SUBJECT]

Class:
[CLASS]

Output:

Week
Topic
Objectives
Activities
"""
},


{
    "category": "CBT Questions",
    "title": "Generate WAEC CBT Questions",
    "school_level": "SECONDARY",
    "subject": "",
    "prompt_text": """
Act as a WAEC examiner.

Generate 50 CBT questions.

Subject:
[SUBJECT]

Topic:
[TOPIC]

Requirements:

A-D options
Correct Answer
Difficulty Level
Explanation
"""
},


{
    "category": "Assignments",
    "title": "Generate Holiday Assignment",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Generate a holiday assignment.

Subject:
[SUBJECT]

Class:
[CLASS]

Include:

Objective Questions
Theory Questions
Project Work
"""
},

{
    "category": "Result Analysis",
    "title": "Class Result Analysis",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Analyze this class result.

Data:

[PASTE SCORES]

Provide:

Highest Score
Lowest Score
Average Score
Pass Rate
Fail Rate
Recommendations
"""
},


{
    "category": "Parent Communication",
    "title": "Generate Parent SMS",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Generate a professional SMS to parents.

Purpose:

[PURPOSE]

Maximum Length:
160 characters
"""
},

{
    "category": "School Administration",
    "title": "Generate PTA Invitation",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Create a PTA meeting invitation.

Date:
[DATE]

Venue:
[VENUE]

Agenda:
[AGENDA]
"""
},

{
    "category": "Admissions & Enrollment",
    "title": "Admission Interview Questions",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Generate admission interview questions.

Class Seeking Admission:
[CLASS]

Include:

Academic Questions
Behaviour Questions
Parent Questions
"""
},


{
    "category": "Teacher Productivity",
    "title": "Generate Weekly Teaching Plan",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Create a weekly teaching plan.

Teacher:
[NAME]

Subjects:
[SUBJECTS]

Classes:
[CLASSES]

Output in timetable format.
"""
},


{
    "category": "Lesson Notes",
    "title": "Complete Lesson Note Generator",
    "school_level": "GENERAL",
    "subject": "",
    "prompt_text": """
Act as an experienced teacher.

Generate a complete lesson note.

Subject:
[SUBJECT]

Class:
[CLASS]

Topic:
[TOPIC]

Sub-topic:
[SUBTOPIC]

Include:

General Objectives
Specific Objectives
Entry Behaviour
Instructional Materials
Presentation
Evaluation
Assignment
Reference

Format professionally.
"""
},

        ]

        for item in prompts:

            # category = PromptCategory.objects.get(
            #     name=item["category"]
            # )

            category, created = PromptCategory.objects.get_or_create(
                name=item["category"],
                defaults={
                    "slug": slugify(item["category"])
                }
            )

            # PromptLibrary.objects.get_or_create(

            #     title=item["title"],

            #     defaults={

            #         "category": category,

            #         "school_level": item["school_level"],

            #         "subject": item["subject"],

            #         "prompt_text": item["prompt_text"],

            #         "is_featured": True,

            #         "is_active": True,

            #     }
            # )

            PromptLibrary.objects.update_or_create(
                title=item["title"],
                defaults={
                    "category": category,
                    "school_level": item["school_level"],
                    "subject": item["subject"],
                    "prompt_text": item["prompt_text"],
                    "is_featured": True,
                    "is_active": True,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Educational Prompts Loaded Successfully."
            )
        )
