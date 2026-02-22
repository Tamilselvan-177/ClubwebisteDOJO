from django.db import models
import datetime


class writeup(models.Model):
    """Club writeup: author writes summary in Markdown; displayed as MD on the site."""
    title = models.CharField(max_length=200)
    date = models.DateField(default=datetime.date.today)
    author = models.CharField(max_length=200)
    category = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=50)
    summary = models.TextField(
        help_text="Write in Markdown. Rendered as Markdown on the website."
    )
    created_at = models.DateTimeField(auto_now_add=True)