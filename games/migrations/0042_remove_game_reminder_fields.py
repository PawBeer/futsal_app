from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0041_backfill_game_notifications"),
    ]

    operations = [
        migrations.RemoveField(model_name="game", name="reminder_enabled"),
        migrations.RemoveField(model_name="game", name="reminder_send_at"),
        migrations.RemoveField(model_name="game", name="reminder_sent_at"),
        migrations.RemoveField(model_name="game", name="standby_reminder_enabled"),
        migrations.RemoveField(model_name="game", name="standby_reminder_send_at"),
        migrations.RemoveField(model_name="game", name="standby_reminder_sent_at"),
    ]
