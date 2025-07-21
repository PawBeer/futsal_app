from django.db import models
import csv
import datetime

# Create your models here.

class Game(models.Model):
    when = models.DateField()
    status = models.CharField(max_length=100)
    description = models.TextField(null=True)
    slot_1 = models.IntegerField(null=True)
    slot_2 = models.IntegerField(null=True)
    slot_3 = models.IntegerField(null=True)
    slot_4 = models.IntegerField(null=True)
    slot_5 = models.IntegerField(null=True)
    slot_6 = models.IntegerField(null=True)
    slot_7 = models.IntegerField(null=True)
    slot_8 = models.IntegerField(null=True)
    slot_9 = models.IntegerField(null=True)
    slot_10 = models.IntegerField(null=True)

    def __str__(self):
        return f"{self.when} - {self.status}"

    def number_of_occupied_slots(self):
        slots = [
            self.slot_1, self.slot_2, self.slot_3, self.slot_4, self.slot_5,
            self.slot_6, self.slot_7, self.slot_8, self.slot_9, self.slot_10
        ]
        sum = 0
        for slot in slots:
            if slot not in (None, 0):
                sum += 1
        return sum


