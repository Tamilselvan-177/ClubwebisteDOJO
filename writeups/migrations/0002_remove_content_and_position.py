# Generated migration: remove content and position from writeup

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("writeups", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="writeup", name="content"),
        migrations.RemoveField(model_name="writeup", name="position"),
    ]
