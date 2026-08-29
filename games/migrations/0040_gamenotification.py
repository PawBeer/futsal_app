import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0039_backfill_standby_reminder_send_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "notification_type",
                    models.CharField(
                        choices=[("weekly", "Weekly"), ("standby", "Standby")],
                        max_length=20,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("send_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="games.game",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="gamenotification",
            constraint=models.UniqueConstraint(
                fields=("game", "notification_type"),
                name="unique_notification_per_game_and_type",
            ),
        ),
    ]
