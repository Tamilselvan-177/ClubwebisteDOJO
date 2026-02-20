import datetime
import os
import uuid
from django.db import models
from django.utils.text import slugify

# Create your models here.
class Blog(models.Model):
    title = models.CharField(max_length=255)
    date = models.DateField(default=datetime.date.today)
    author = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    desc = models.CharField(max_length=500)
    body = models.TextField()
    slug = models.SlugField(unique=True, blank=True, null=True)

    def blog_cover_upload_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        return f"blogs/covers/{uuid.uuid4()}{ext}"

    cover_image = models.ImageField(
        upload_to=blog_cover_upload_path,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Blog.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
