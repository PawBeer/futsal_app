from django.core.management.base import BaseCommand
from django.utils import timezone

from games.helpers.notification_helper import send_standby_availability_reminders
from games.models import Game, GameStatus


class Command(BaseCommand):
    help = (
        "Sends the standby availability invite for the single nearest upcoming "
        "Planned game whose configured send date/time "
        "(Game.standby_reminder_send_at, editable per game, default 1 day "
        "before kickoff) has arrived and hasn't already been sent: asks every "
        "player currently on the standby list whether they'd like to play. "
        "Intended to be triggered once daily by an external cron."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        game = (
            Game.objects.filter(
                status=GameStatus.PLANNED,
                when__gte=now.date(),
                standby_reminder_enabled=True,
                standby_reminder_send_at__isnull=False,
                standby_reminder_send_at__lte=now,
                standby_reminder_sent_at__isnull=True,
            )
            .order_by("when")
            .first()
        )

        if game is None:
            self.stdout.write("No game due for a standby reminder today.")
            return

        sent_count = send_standby_availability_reminders(game)

        game.standby_reminder_sent_at = timezone.now()
        game.save(update_fields=["standby_reminder_sent_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} standby reminder(s) for game {game.id} ({game.when})."
            )
        )
