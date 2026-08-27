from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from games.helpers import game_helper, token_helper
from games.mailer import (
    send_weekly_availability_reminder_email,
    send_weekly_game_cancelled_notice_email,
)
from games.models import Game, GameStatus, StatusChoices


class Command(BaseCommand):
    help = (
        "Sends the weekly reminder for the single nearest upcoming game whose "
        "configured send date/time (Game.reminder_send_at, editable per game, "
        "default 2 days before kickoff) has arrived and hasn't already been "
        "sent: a 'who can't play' availability nudge for Planned games, or a "
        "cancellation notice for Cancelled games. Intended to be triggered "
        "once daily by an external cron."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        game = (
            Game.objects.filter(
                status__in=[GameStatus.PLANNED, GameStatus.CANCELLED],
                when__gte=now.date(),
                reminder_enabled=True,
                reminder_send_at__isnull=False,
                reminder_send_at__lte=now,
                reminder_sent_at__isnull=True,
            )
            .order_by("when")
            .first()
        )

        if game is None:
            self.stdout.write("No game due for a reminder today.")
            return

        planned_players = game_helper.get_players_by_status(
            [StatusChoices.PLANNED], game
        )

        sent_count = 0
        for player in planned_players:
            if not player.user or not player.user.email:
                continue

            if game.status == GameStatus.CANCELLED:
                send_weekly_game_cancelled_notice_email(player, game)
            else:
                token = token_helper.make_cancel_token(game, player)
                cancel_url = settings.SITE_URL + reverse(
                    "cancel_participation_url", args=[token]
                )
                send_weekly_availability_reminder_email(player, game, cancel_url)
            sent_count += 1

        game.reminder_sent_at = timezone.now()
        game.save(update_fields=["reminder_sent_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} reminder(s) for game {game.id} ({game.when}, {game.status})."
            )
        )
