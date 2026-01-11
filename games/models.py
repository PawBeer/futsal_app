from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models

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


class TeamChoices(models.TextChoices):
    BLACK = "black", "Black"
    WHITE = "white", "White"


class GamePlayer(models.Model):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="players"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="games"
    )
    team = models.CharField(
        max_length=10, choices=TeamChoices.choices
    )

    class Meta:
        unique_together = ("game", "player")

    def __str__(self):
        return f"{self.player} ({self.team}) - {self.game}"


class GoalEvent(models.Model):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="goals"
    )
    team = models.CharField(
        max_length=10, choices=TeamChoices.choices
    )
    scorer = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True
    )
    own_goal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        og = " (OG)" if self.own_goal else ""
        return f"{self.game} | {self.scorer}{og} | {self.created_at}'"
