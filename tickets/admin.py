# tickets/admin.py
from django.contrib import admin
from .models import Ticket, Comment
from import_export.admin import ImportExportModelAdmin

@admin.register(Ticket)
class TicketAdmin(ImportExportModelAdmin):
    list_display = ['id', 'title', 'author', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['title', 'description', 'author__username']

@admin.register(Comment)
class CommentAdmin(ImportExportModelAdmin):
    list_display = ['id', 'ticket', 'author', 'created_at']
    search_fields = ['text']