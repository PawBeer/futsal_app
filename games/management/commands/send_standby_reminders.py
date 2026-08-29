from django.core.management.base import BaseCommand
from django.utils import timezone

from games.helpers.notification_helper import send_standby_availability_reminders
from games.models import Game, GameStatus, NotificationType


class Command(BaseCommand):
    help = (
        "Sends the standby availability invite for the single nearest upcoming "
        "Planned game whose configured send date/time "
        "(GameNotification.send_at for the standby type, editable per game, "
        "default 1 day before kickoff) has arrived and hasn't already been "
        "sent: asks every "
        "player currently on the standby list whether they'd like to play. "
        "Intended to be polled every few minutes (e.g. by cron_entrypoint.sh); "
        "safe to run more often since it no-ops once already sent."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        game = (
            Game.objects.filter(
                status=GameStatus.PLANNED,
                when__gte=now.date(),
                notifications__notification_type=NotificationType.STANDBY,
                notifications__enabled=True,
                notifications__send_at__isnull=False,
                notifications__send_at__lte=now,
                notifications__sent_at__isnull=True,
            )
            .order_by("when")
            .first()
        )

        if game is None:
            self.stdout.write("No game due for a standby reminder today.")
            return

        sent_count = send_standby_availability_reminders(game)

        standby_reminder = game.standby_reminder
        standby_reminder.sent_at = timezone.now()
        standby_reminder.save(update_fields=["sent_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} standby reminder(s) for game {game.id} ({game.when})."
            )
        )
