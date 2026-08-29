from django.core.management.base import BaseCommand
from django.utils import timezone

from games.helpers.notification_helper import send_weekly_reminders_now
from games.models import Game, GameStatus, NotificationType


class Command(BaseCommand):
    help = (
        "Sends the weekly reminder for the single nearest upcoming game whose "
        "configured send date/time (GameNotification.send_at for the weekly "
        "type, editable per game, default 2 days before kickoff) has arrived "
        "and hasn't already been sent: a 'who can't play' availability nudge "
        "for Planned games, or a cancellation notice for Cancelled games. "
        "Intended to be polled every few minutes (e.g. by cron_entrypoint.sh); "
        "safe to run more often since it no-ops once already sent."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        game = (
            Game.objects.filter(
                status__in=[GameStatus.PLANNED, GameStatus.CANCELLED],
                when__gte=now.date(),
                notifications__notification_type=NotificationType.WEEKLY,
                notifications__enabled=True,
                notifications__send_at__isnull=False,
                notifications__send_at__lte=now,
                notifications__sent_at__isnull=True,
            )
            .order_by("when")
            .first()
        )

        if game is None:
            self.stdout.write("No game due for a reminder today.")
            return

        sent_count = send_weekly_reminders_now(game)

        weekly_reminder = game.weekly_reminder
        weekly_reminder.sent_at = timezone.now()
        weekly_reminder.save(update_fields=["sent_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} reminder(s) for game {game.id} ({game.when}, {game.status})."
            )
        )
