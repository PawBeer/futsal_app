from django.core.validators import MinLengthValidator, MaxLengthValidator, MinValueValidator, MaxValueValidator
from django.db import models

# Create your models here.
class Player(models.Model):
    name = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    surname = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    email = models.CharField(max_length=255, validators=[MinLengthValidator(3)])
    mobile_number = models.IntegerField(validators=[MinValueValidator(100000000), MaxValueValidator(999999999)])
    nickname = models.CharField(max_length=255, default='N/A', validators=[MinLengthValidator(3)])

    def __str__(self):
        if self.nickname != 'N/A':
            return f'{self.nickname}'
        return f'{self.name} {self.surname}'