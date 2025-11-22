from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models

User = get_user_model()

phone_validator = RegexValidator(
    regex=r"^(\d{9})$", message="Mobile number must contain exactly 9 digits"
)


class Player(models.Model):
    ROLE_ACTIVE = "Active"
    ROLE_INACTIVE = "Inactive"
    ROLE_PERMANENT = "Permanent"

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    ROLE_CHOICES = [
        (ROLE_ACTIVE, ROLE_ACTIVE),
        (ROLE_INACTIVE, ROLE_INACTIVE),
        (ROLE_PERMANENT, ROLE_PERMANENT),
    ]
    mobile_number = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r"^\d{9}$", message="Mobile number must contain exactly 9 digits"
            )
        ],
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_ACTIVE)

    def __str__(self):
        return self.user.username if self.user else "(No user)"


class Game(models.Model):
    PLANNED = "Planned"
    PLAYED = "Played"
    CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (PLANNED, PLANNED),
        (PLAYED, PLAYED),
        (CANCELLED, CANCELLED),
    ]
    when = models.DateField()
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default=PLANNED)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.when} - {self.status}"

class PlayerStatus(models.Model):
    PLANNED = "planned"
    CANCELLED = "cancelled"
    CONFIRMED = "confirmed"
    RESERVED = "reserved"
    RESTING = "resting"

    STATUS_CHOICES = [
        (PLANNED, PLANNED),
        (CANCELLED, CANCELLED),
        (CONFIRMED, CONFIRMED),
        (RESERVED, RESERVED),
        (RESTING, RESTING),
    ]
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    date_start = models.DateField()
    date_end = models.DateField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=RESTING)
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
    status = models.CharField(max_length=50, choices=PlayerStatus.STATUS_CHOICES, default=PlayerStatus.RESTING)
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} - {self.status} on {self.game}"


