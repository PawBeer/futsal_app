from games.models import Game, GameStatus

from .base import BaseTestCase


class GameModelTests(BaseTestCase):

    def test_game_creation(self):
        game = Game.objects.create(
            when="2024-07-01", description="just a test game", status=GameStatus.PLANNED
        )
        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(game.status, GameStatus.PLANNED)
        self.assertEqual(str(game), "2024-07-01 - Planned")
