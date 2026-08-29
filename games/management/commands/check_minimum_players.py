from django.core.management.base import BaseCommand
from django.utils import timezone

from games.helpers import game_helper, notification_helper
from games.models import Game, GameStatus, NotificationType, StatusChoices


class Command(BaseCommand):
    help = (
        "Checks the single nearest upcoming Planned game whose configured "
        "check date/time (GameNotification.send_at for the "
        "min_players_check type, editable per game, default game day at "
        "13:00) has arrived and hasn't already been checked. If the number "
        "of Planned/Confirmed players is below the game's minimum_players "
        "threshold (default 8), cancels the game and immediately emails "
        "every Planned/Confirmed player the cancellation notice, same as a "
        "manual cancellation. Intended to be polled every few minutes (e.g. "
        "by cron_entrypoint.sh); safe to run more often since it no-ops "
        "once already checked."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        game = (
            Game.objects.filter(
                status=GameStatus.PLANNED,
                when__gte=now.date(),
                notifications__notification_type=NotificationType.MIN_PLAYERS_CHECK,
                notifications__enabled=True,
                notifications__send_at__isnull=False,
                notifications__send_at__lte=now,
                notifications__sent_at__isnull=True,
            )
            .order_by("when")
            .first()
        )

        if game is None:
            self.stdout.write("No game due for a minimum players check today.")
            return

        players_count = len(
            game_helper.get_players_by_status(
                [StatusChoices.PLANNED, StatusChoices.CONFIRMED], game
            )
        )

        cancelled = players_count < game.minimum_players
        if cancelled:
            game.status = GameStatus.CANCELLED
            game.save(update_fields=["status"])
            notification_helper.notify_players_of_cancellation(game)

        min_players_check = game.min_players_check
        min_players_check.sent_at = now
        min_players_check.save(update_fields=["sent_at"])

        if cancelled:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Game {game.id} ({game.when}) cancelled: only "
                    f"{players_count}/{game.minimum_players} players."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Game {game.id} ({game.when}) has enough players "
                    f"({players_count}/{game.minimum_players})."
                )
            )
