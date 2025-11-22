from games.models import Player

from .base import BaseTestCase


class PlayerModelTests(BaseTestCase):

    def test_players_various_roles(self):

        self.assertEqual(Player.objects.all().count(), 4)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_PERMANENT).count(), 3)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_INACTIVE).count(), 0)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_ACTIVE).count(), 1)
