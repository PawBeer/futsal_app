from django.db import models

# Create your models here.
class Player(models.Model):
    name = models.CharField(max_length=255)
    surname = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    mobile_number = models.IntegerField()
    nickname = models.CharField(max_length=255, default='N/A')

    def __str__(self):
        if self.nickname != 'N/A':
            return f'{self.nickname}'
        return f'{self.name} {self.surname}'