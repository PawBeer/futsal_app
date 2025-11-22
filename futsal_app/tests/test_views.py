from games.models import BookingHistoryForGame, Game, PlayerStatus

from .base import BaseTestCase


class AddGameViewTests(BaseTestCase):

    def test_post_with_set_players_creates_bookings_for_permanent_and_active(self):
        data = {
            "when": "2025-01-01",
            "status": "Planned",
            "description": "Test game with players",
            "set_players": "on",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        # view should redirect after successful POST
        self.assertEqual(response.status_code, 302)

        # the game should be created
        game = Game.objects.get(description="Test game with players")

        # bookings should be created for Permanent (planned) and Active (reserved) players
        bookings = BookingHistoryForGame.objects.filter(game=game)
        self.assertEqual(bookings.count(), 4)

        self.assertEqual(
            BookingHistoryForGame.objects.filter(
                game=game, status=PlayerStatus.PLANNED
            ).count(),
            3,
        )
        self.assertEqual(
            BookingHistoryForGame.objects.filter(
                game=game, status=PlayerStatus.RESERVED
            ).count(),
            1,
        )

    def test_post_without_set_players_creates_game_but_no_bookings(self):
        data = {
            "when": "2025-02-02",
            "status": "Planned",
            "description": "Test game without players",
            # no "set_players" key
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(description="Test game without players")
        bookings = BookingHistoryForGame.objects.filter(game=game)
        self.assertEqual(bookings.count(), 0)
