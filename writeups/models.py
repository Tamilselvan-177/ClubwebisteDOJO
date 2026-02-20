from django.db import models
import datetime

# Create your models here.
class writeup(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField(default=datetime.date.today)
    author = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    category = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=50)
    summary = models.TextField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)