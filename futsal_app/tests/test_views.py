from games.helpers import game_helper
from games.helpers.game_helper import get_players_by_status, get_total_players_for_game
from games.models import BookingHistoryForGame, Game, Player, PlayerStatus

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

    def test_transition_from_reserved_to_confirmed(self):
        data = {
            "when": "2025-03-03",
            "status": "Planned",
            "description": "Test game with reserved player",
            "set_players": "yes",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(when="2025-03-03")

        # get a reserved player
        reserved_player = (
            BookingHistoryForGame.objects.filter(
                game=game, status=PlayerStatus.RESERVED
            )
            .order_by("-creation_date")
            .first()
        ).player

        # now we have 3 players booked for the game (3 permanent /planned)
        self.assertEqual(get_total_players_for_game(game), 3)

        data = {
            "player_id": reserved_player.id,
            "checked": "on",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)

        # now the reserved player should be awaiting hence still 3 players booked
        self.assertEqual(get_total_players_for_game(game), 3)

    def test_transition_from_reserved_to_awaiting_to_confirmed(self):
        data = {
            "when": "2025-03-03",
            "status": "Planned",
            "description": "Test game with reserved player",
            "set_players": "yes",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(when="2025-03-03")

        # get a reserved player
        reserved_player = (
            BookingHistoryForGame.objects.filter(
                game=game, status=PlayerStatus.RESERVED
            )
            .order_by("-creation_date")
            .first()
        ).player

        # now we have 3 players booked for the game (3 permanent /planned)
        self.assertEqual(get_total_players_for_game(game), 3)

        data = {
            "player_id": reserved_player.id,
            "checked": "on",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)

        # now the reserved player should be awaiting hence still 3 players booked
        self.assertEqual(get_total_players_for_game(game), 3)

        # lets cancel one planned player and that would move awaiting to confirmed
        bolek_player = Player.objects.get(user=self.user_1_per)
        data = {
            "player_id": bolek_player.id,
            "checked": "off",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            len(game_helper.get_players_by_status([PlayerStatus.AWAITING], game)), 0
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([PlayerStatus.PLANNED], game)), 2
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([PlayerStatus.CONFIRMED], game)), 1
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([PlayerStatus.CANCELLED], game)), 1
        )
        self.assertEqual(get_total_players_for_game(game), 3)
