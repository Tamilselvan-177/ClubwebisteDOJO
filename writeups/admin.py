from django.contrib import admin
from .models import writeup


@admin.register(writeup)
class WriteupAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "category", "difficulty", "date", "created_at"]
    list_filter = ["category", "difficulty", "date"]
    search_fields = ["title", "author", "summary"]
    date_hierarchy = "date"
    fields = ["title", "date", "author", "category", "difficulty", "summary"]
    readonly_fields = ["created_at"]