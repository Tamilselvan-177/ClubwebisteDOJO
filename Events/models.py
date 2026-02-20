import datetime
import os
import uuid
from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    title = models.CharField(max_length=200)
    desc = models.CharField(max_length=300)
    date = models.DateField(default=datetime.date.today)
    slug = models.SlugField(unique=True, blank=True)

    cover_image = models.ImageField(
        upload_to="events/covers/",
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        # Automatically generate slug from title
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


def event_image_upload_path(instance, filename):
    """
    Creates folder structure:
    media/events/<event-slug>/<random-uuid>.jpg
    """
    extension = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{extension}"

    return os.path.join(
        "events",
        instance.event.slug,
        new_filename
    )


class EventImage(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to=event_image_upload_path)

    def __str__(self):
        return f"{self.event.title} Image"