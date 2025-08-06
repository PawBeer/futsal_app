from django.db import models
import csv
import datetime
from django.core.validators import MinLengthValidator, MaxLengthValidator, MinValueValidator, MaxValueValidator
from django.core.validators import RegexValidator
from django.contrib.auth.models import User

# Create your models here.

phone_validator = RegexValidator(
    regex=r'^(\d{9})$',
    message="Mobile number must contain exactly 9 digits"
)


class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    ROLE_CHOICES = [('Active','Active'),('Inactive','Inactive'),('Permanent','Permanent')]
    mobile_number = models.CharField(
        max_length=9,
        validators=[RegexValidator(regex=r'^\d{9}$', message="Mobile number must contain exactly 9 digits")]
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Active')

    def __str__(self):
        return self.user.username if self.user else "(No user)"

    def get_latest_booking_for_game(self, game):
        return BookingHistoryForGame.objects.filter(player=self, game=game).order_by('-creation_date').first()


class PlayerStatus(models.Model):
    player_status = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.player_status

class Game(models.Model):
    STATUS_CHOICES = [
        ('Planned', 'Planned'),
        ('Played', 'Played'),
        ('Cancelled', 'Cancelled'),
    ]
    when = models.DateField()
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='Planned')
    description = models.TextField(null=True, blank = True)

    def __str__(self):
        return f"{self.when} - {self.status}"


class BookingHistoryForGame(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='status_history')
    player_status = models.ForeignKey(PlayerStatus, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player} - {self.player_status} on {self.game}"
