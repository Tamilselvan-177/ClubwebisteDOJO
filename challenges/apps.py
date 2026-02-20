from django.apps import AppConfig


class ChallengesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'challenges'
    verbose_name = '🚩 CTF - Challenges'
    
    def ready(self):
        import challenges.signals  # noqa