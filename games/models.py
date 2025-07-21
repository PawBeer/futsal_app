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


    @staticmethod
    def get_all_games():
        with open('games/migrations/games.csv', 'r', encoding='utf-8') as games:
            reader = csv.DictReader(games, delimiter=',')

            return list(map(
                lambda row: Game(
                    row['id'],
                    row['when'],
                    row['status'],
                )
            , reader))

    @staticmethod
    def get_game_by_id(game_id):
        with open('games/migrations/games.csv', 'r', encoding='utf-8') as games:
            reader = csv.DictReader(games, delimiter=',')

            for row in reader:
                if row['id'] == game_id:
                    return Game(
                        row['id'],
                        row['when'],
                        row['status'],
                        )

