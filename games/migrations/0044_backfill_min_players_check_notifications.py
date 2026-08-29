from datetime import datetime, time

from django.db import migrations
from django.utils import timezone


def backfill_min_players_check_notifications(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    GameNotification = apps.get_model("games", "GameNotification")

    now = timezone.now()
    notifications = []
    for game in Game.objects.all():
        send_at = timezone.make_aware(datetime.combine(game.when, time(13, 0)))
        # Don't retroactively check games whose check time has already
        # passed - only newly-created games should be evaluated going
        # forward.
        sent_at = None if send_at > now else now
        notifications.append(
            GameNotification(
                game=game,
                notification_type="min_players_check",
                enabled=True,
                send_at=send_at,
                sent_at=sent_at,
            )
        )
    GameNotification.objects.bulk_create(notifications)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0043_game_minimum_players_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_min_players_check_notifications, noop_reverse),
    ]
