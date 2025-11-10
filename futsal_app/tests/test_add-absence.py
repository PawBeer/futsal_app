from datetime import datetime
from django.test import TestCase
from django.utils import timezone
from games.models import PlayerStatusManager, PlayerStatus, Game, BookingHistoryForGame, Player
from games import views
from .base import BaseTestCase


class SimpleAddAbsenceTest(BaseTestCase):

    def test_add_absence_creates_records(self):
        player = Player.objects.get(user=self.user_1_per)

        PlayerStatus.objects.create(player_status='resting')
        game = Game.objects.create(when=datetime(2025, 4, 10), description="Game for absence test")

        data = {
            'player': player.pk,
            'date_start': '2025-04-09',
            'date_end': '2025-04-20',
            'status': 'resting',
            'description': 'Simple absence test',
        }
        request = self.factory.post('/games/add_absence/', data)
        request.user = self.superuser

        response = views.add_absence(request)

        self.assertEqual(response.status_code, 302)

        self.assertTrue(PlayerStatusManager.objects.filter(player=player).exists())
        self.assertEqual(PlayerStatusManager.objects.filter(player=player), 'resting')
        self.assertTrue(BookingHistoryForGame.objects.filter(player=player, game=game).exists())
        self.assertEqual(game.player_status.player_status, 'cancelled')
