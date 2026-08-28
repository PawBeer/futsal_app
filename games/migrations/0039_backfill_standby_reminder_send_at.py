from datetime import datetime, time, timedelta

from django.db import migrations
from django.utils import timezone


def backfill_standby_reminder_send_at(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    for game in Game.objects.filter(standby_reminder_send_at__isnull=True):
        game.standby_reminder_send_at = timezone.make_aware(
            datetime.combine(game.when - timedelta(days=1), time(8, 0))
        )
        game.save(update_fields=["standby_reminder_send_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0038_game_standby_reminder_enabled_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_standby_reminder_send_at, noop_reverse),
    ]
