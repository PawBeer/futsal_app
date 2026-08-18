from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


class PlayerRole(models.TextChoices):
    ACTIVE = "Active", "Active"
    INACTIVE = "Inactive", "Inactive"
    PERMANENT = "Permanent", "Permanent"


class Player(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    mobile_number = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r"^\d{9}$", message="Mobile number must contain exactly 9 digits"
            )
        ],
    )
    role = models.CharField(
        max_length=10, choices=PlayerRole.choices, default=PlayerRole.ACTIVE
    )
    is_accountant = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username if self.user else "(No user)"


class GameStatus(models.TextChoices):
    PLANNED = "Planned", "Planned"
    PLAYED = "Played", "Played"
    CANCELLED = "Cancelled", "Cancelled"


class Game(models.Model):

    when = models.DateField()
    status = models.CharField(
        max_length=100, choices=GameStatus.choices, default=GameStatus.PLANNED
    )
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.when} - {self.status}"


# pylint: disable=too-many-ancestors
class StatusChoices(models.TextChoices):
    PLANNED = "planned", "Planned"
    CANCELLED = "cancelled", "Cancelled"
    CONFIRMED = "confirmed", "Confirmed"
    RESERVED = "reserved", "Reserved"
    RESTING = "resting", "Resting"
    # the player is happy to play (responded positive) but the booking is not yet confirmed
    AWAITING = "awaiting", "Awaiting"

    @classmethod
    def filtered_choices(cls, *, exclude=None):
        exclude = set(exclude or [])
        return [(value, label) for value, label in cls.choices if value not in exclude]


class PlayerStatus(models.Model):

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    date_start = models.DateField()
    date_end = models.DateField()
    status = models.CharField(
        max_length=50, choices=StatusChoices.choices, default=StatusChoices.RESTING
    )
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.player} from {self.date_start} to {self.date_end} - {self.status}"
        )


class BookingHistoryForGame(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.CharField(
        max_length=50, choices=StatusChoices.choices, default=StatusChoices.RESTING
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} - {self.status} on {self.game}"


class ChatMessage(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_messages"
    )
    message = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} @ {self.created_at}: {self.message[:30]}"


class TeamChoices(models.TextChoices):
    BLACK = "black", "Black"
    WHITE = "white", "White"


class GoalEvent(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="goals")
    team = models.CharField(max_length=10, choices=TeamChoices.choices)
    scorer = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    own_goal = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        own_goal = " (OG)" if self.own_goal else ""
        return f"{self.game} | {self.scorer}{own_goal} | {self.created_at.strftime('%H:%M:%S')}"


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
                fields=["settlement_run", "player"],
                name="unique_charge_per_player_per_run",
            )
        ]

    def __str__(self):
        return f"{self.player} - {self.amount} ({self.settlement_run})"


class SubstitutePayment(models.Model):
    """
    Tracks the peer-to-peer payment for one game: a substitute (confirmed)
    player owes the cancelled player they filled in for the game price.
    """

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="substitute_payments"
    )
    cancelled_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="received_substitute_payments"
    )
    substitute_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="sent_substitute_payments"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "cancelled_player", "substitute_player"],
                name="unique_substitute_payment_per_game",
            )
        ]

    def __str__(self):
        return f"{self.substitute_player} -> {self.cancelled_player} ({self.game})"
