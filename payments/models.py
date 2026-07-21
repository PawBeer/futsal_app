from django.contrib.auth import get_user_model
from django.db import models

from games.models import Player

User = get_user_model()


class GamePrice(models.Model):
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    valid_from = models.DateField(unique=True)

    class Meta:
        ordering = ["-valid_from"]

    def __str__(self):
        return f"{self.amount} from {self.valid_from}"


class SettlementRun(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    send_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "month"], name="unique_settlement_run_period"
            )
        ]

    def __str__(self):
        return f"Settlement {self.year}-{self.month:02d}"


class PlayerCharge(models.Model):
    settlement_run = models.ForeignKey(
        SettlementRun, on_delete=models.CASCADE, related_name="charges"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="payment_charges"
    )
    amount = models.DecimalField(max_digits=7, decimal_places=2)
    game_count = models.PositiveIntegerField()
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_charges_marked",
    )

    class Meta:
        ordering = ["player__user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["settlement_run", "player"], name="unique_charge_per_player_per_run"
            )
        ]

    def __str__(self):
        return f"{self.player} - {self.amount} ({self.settlement_run})"
