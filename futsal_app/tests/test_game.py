from .base import BaseTestCase

from games.models import Game


class GameModelTests(BaseTestCase):

    def test_game_creation(self):
        game = Game.objects.create(
            when="2024-07-01", description="just a test game", status=Game.PLANNED
        )
        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(game.status, Game.PLANNED)
        self.assertEqual(str(game), "2024-07-01 - Planned")
