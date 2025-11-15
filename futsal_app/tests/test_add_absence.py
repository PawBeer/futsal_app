from datetime import datetime
from django.test import Client, TestCase
from django.utils import timezone
from games.models import PlayerStatus, Game, BookingHistoryForGame, Player
from games import views
from .base import BaseTestCase
from django.urls import reverse

class SimpleAddAbsenceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_add_absence_creates_records(self):
        player = Player.objects.get(user=self.user_1_per)

        game = Game.objects.create(when=datetime(2025, 11, 16), description="Game for absence test")

        booking_set_user_1_per = BookingHistoryForGame.objects.create(game=game, player=player, player_status='planned')

        data = {
            'player': player.pk,
            'date_start': '2025-11-15',
            'date_end': '2025-11-20',
            'status': 'resting',
            'description': 'Simple absence test',
        }
        self.client.force_login(self.superuser)
        url = reverse('add_absence_url')
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)

        self.assertTrue(PlayerStatus.objects.filter(player=player).exists())
        status_obj = PlayerStatus.objects.get(player=player)
        self.assertEqual(status_obj.status, 'resting')

        booking_obj = BookingHistoryForGame.objects.filter(player=player, game=game).last()
        self.assertIsNotNone(booking_obj)
        self.assertEqual(booking_obj.status, 'cancelled')
