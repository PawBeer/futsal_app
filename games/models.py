from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import (
    RegexValidator,
)
from django.db import models

# Create your models here.

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

    def get_display_name(self):
        display_mode = getattr(settings, "DISPLAY_NAME_MODE", "username")
        if display_mode == "username" and self.user:
            return self.user.username
        elif display_mode == "full_name" and self.user:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip()
            return full_name if full_name else self.user.username
        return "Unknown Player"

    def __str__(self):
        return self.user.username if self.user else "(No user)"

    def get_latest_booking_for_game(self, game):
        return (
            BookingHistoryForGame.objects.filter(player=self, game=game)
            .order_by("-creation_date")
            .first()
        )


class PlayerStatus(models.Model):
    player_status = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.player_status


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


class BookingHistoryForGame(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="status_history"
    )
    player_status = models.ForeignKey(PlayerStatus, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} - {self.player_status} on {self.game}"
