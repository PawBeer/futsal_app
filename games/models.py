from django.db import models
import csv
import datetime
from django.core.validators import MinLengthValidator, MaxLengthValidator, MinValueValidator, MaxValueValidator
from django.core.validators import RegexValidator

# Create your models here.

phone_validator = RegexValidator(
    regex=r'^(\d{9})$',
    message="Mobile number must contain exactly 9 digits"
)


class Player(models.Model):
    ROLE_CHOICES = [('Active','Active'),('Inactive','Inactive'),('Permanent','Permanent')]
    name = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    surname = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    nickname = models.CharField(max_length=255, default='N/A', validators=[MinLengthValidator(3)])
    email = models.EmailField(max_length=255, validators=[MinLengthValidator(3)])
    mobile_number = models.CharField(
        max_length=9,
        validators=[RegexValidator(regex=r'^\d{9}$', message="Mobile number must contain exactly 9 digits")]
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Active')

    def __str__(self):
        return self.nickname if self.nickname != "N/A" else f"{self.name} {self.surname}"


class PlayerStatus(models.Model):
    player_status_name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.player_status_name

class Game(models.Model):
    when = models.DateField()
    status = models.CharField(max_length=100, default='planned')
    description = models.TextField(null=True, blank = True)
    slot_1 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_1_games')
    slot_2 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_2_games')
    slot_3 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_3_games')
    slot_4 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_4_games')
    slot_5 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_5_games')
    slot_6 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_6_games')
    slot_7 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_7_games')
    slot_8 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_8_games')
    slot_9 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_9_games')
    slot_10 = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='slot_10_games')

    def __str__(self):
        return f"{self.when} - {self.status}"

    def number_of_occupied_slots(self):
        slots = [
            self.slot_1, self.slot_2, self.slot_3, self.slot_4, self.slot_5,
            self.slot_6, self.slot_7, self.slot_8, self.slot_9, self.slot_10
        ]
        count = 0
        for slot in slots:
            if slot is not None:
                count += 1
        return count

class BookingHistoryForGame(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='status_history')
    player_status = models.ForeignKey(PlayerStatus, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('player', 'game')

    def __str__(self):
        return f"{self.player} - {self.player_status} on {self.game}"
