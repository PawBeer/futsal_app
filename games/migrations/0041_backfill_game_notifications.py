from django.db import migrations


def backfill_game_notifications(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    GameNotification = apps.get_model("games", "GameNotification")

    notifications = []
    for game in Game.objects.all():
        notifications.append(
            GameNotification(
                game=game,
                notification_type="weekly",
                enabled=game.reminder_enabled,
                send_at=game.reminder_send_at,
                sent_at=game.reminder_sent_at,
            )
        )
        notifications.append(
            GameNotification(
                game=game,
                notification_type="standby",
                enabled=game.standby_reminder_enabled,
                send_at=game.standby_reminder_send_at,
                sent_at=game.standby_reminder_sent_at,
            )
        )
    GameNotification.objects.bulk_create(notifications)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0040_gamenotification"),
    ]

    operations = [
        migrations.RunPython(backfill_game_notifications, noop_reverse),
    ]
