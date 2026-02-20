from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events_ctf'
    verbose_name = '🎯 CTF - Events'
    
    def ready(self):
        import events_ctf.signals  # noqa
