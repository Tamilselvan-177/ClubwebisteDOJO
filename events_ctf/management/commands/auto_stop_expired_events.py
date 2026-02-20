"""
Management command to manually trigger auto-stop for expired events.
Usage: python manage.py auto_stop_expired_events
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from events_ctf.models import Event


class Command(BaseCommand):
    help = 'Manually auto-stop events that have passed their end_time'

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f"Current time: {now}")
        
        # Find all active events that should be stopped
        active_events = Event.objects.filter(
            is_active=True,
            end_time__lte=now
        ).exclude(contest_state='stopped')
        
        if not active_events.exists():
            self.stdout.write(self.style.SUCCESS('✓ No events need to be stopped'))
            return
        
        stopped_count = 0
        for event in active_events:
            self.stdout.write(f"\nProcessing: {event.name} ({event.year})")
            self.stdout.write(f"  End time: {event.end_time}")
            self.stdout.write(f"  Current state: {event.contest_state}")
            self.stdout.write(f"  Is active: {event.is_active}")
            
            # Auto-stop the event
            was_stopped = event.auto_stop_if_expired()
            
            if was_stopped:
                stopped_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ STOPPED"))
                self.stdout.write(f"    - Contest state: {event.contest_state}")
                self.stdout.write(f"    - Is active: {event.is_active}")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Already stopped or error"))
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Total stopped: {stopped_count} event(s)"))
