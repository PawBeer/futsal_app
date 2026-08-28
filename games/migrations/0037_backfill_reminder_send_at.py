from datetime import datetime, time, timedelta

from django.db import migrations
from django.utils import timezone


def backfill_reminder_send_at(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    for game in Game.objects.filter(reminder_send_at__isnull=True):
        game.reminder_send_at = timezone.make_aware(
            datetime.combine(game.when - timedelta(days=2), time(8, 0))
        )
        game.save(update_fields=["reminder_send_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0036_remove_game_reminder_time_game_reminder_send_at"),
    ]

    operations = [
        migrations.RunPython(backfill_reminder_send_at, noop_reverse),
    ]
