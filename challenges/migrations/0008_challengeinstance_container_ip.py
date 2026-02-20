# Generated migration for adding container_ip field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challenges', '0007_challenge_difficulty'),
    ]

    operations = [
        migrations.AddField(
            model_name='challengeinstance',
            name='container_ip',
            field=models.GenericIPAddressField(blank=True, help_text='Docker container IP address', null=True),
        ),
    ]
