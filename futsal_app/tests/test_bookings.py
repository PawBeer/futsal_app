from games.helpers import game_helper, player_helper
from games.models import BookingHistoryForGame, Game, PlayerStatus

from .base import BaseTestCase


class BookingModelTests(BaseTestCase):
    """
    BookingModelTests

    Unit tests for booking-related model behavior and helper utilities.

    Tests included:
    - test_booking_creation
        Confirms a BookingHistoryForGame instance can be created for a Game and a Player
        with a given PlayerStatus. Asserts the booking count increments and that the
        created booking references the expected game, player and status.

    - test_get_latest_booking_for_game
        Verifies that player_helper.get_latest_booking_for_game(player, game)
        returns the most recent BookingHistoryForGame for the given player and game.
        The test creates two bookings for the same player and game with different
        PlayerStatus values (planned then confirmed) and asserts the helper returns
        the later (confirmed) booking.

    - test_get_total_players_for_game
        Validates game_helper.get_total_players_for_game(game) computes the expected
        number of players for a game, considering the latest booking status for each
        player. The test sets up multiple bookings with statuses including confirmed,
        planned, and reserved, asserts the initial total counts only the relevant
        statuses (confirmed/planned), then creates a subsequent booking that changes
        a player's status to cancelled and asserts the total is updated accordingly.

    Assumptions and fixtures:
    - Tests use Django ORM model factories/fixtures available on self (e.g.
      self.user_1_per.player, self.user_2_per.player, self.user_3_per.player,
      self.user_4_act.player).
    - PlayerStatus objects for keys "planned", "confirmed", "reserved", and
      "cancelled" exist in the test database.
    - Game.PLANNED is a valid status constant.
    - The "latest" booking is determined by creation order/timestamp as relied on by
      player_helper.get_latest_booking_for_game.
    - Tests operate against the test database and depend on helpers named
      player_helper and game_helper to implement query logic used by assertions.

    Behavioral notes:
    - The tests assert state based on the most recent booking per player per game,
      which implies booking history is append-only and helper functions should
      consider only the newest entry when deriving current player participation.
    - Side effects (creating BookingHistoryForGame) are intended and expected to
      modify the database state for subsequent assertions within each test.
    """

    def test_booking_creation(self):

        game = Game.objects.create(
            when="2024-08-01", description="booking test game", status=Game.PLANNED
        )
        player_status = PlayerStatus.objects.get(player_status="planned")
        booking = BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_1_per.player,
            player_status=player_status,
        )
        self.assertEqual(BookingHistoryForGame.objects.count(), 1)
        self.assertEqual(booking.player, self.user_1_per.player)
        self.assertEqual(booking.game, game)
        self.assertEqual(booking.player_status, player_status)

    def test_get_latest_booking_for_game(self):
        game = Game.objects.create(
            when="2024-09-01",
            description="latest booking test game",
            status=Game.PLANNED,
        )
        player_status_planned = PlayerStatus.objects.get(player_status="planned")
        player_status_confirmed = PlayerStatus.objects.get(player_status="confirmed")

        # Create two bookings for the same player and game
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            player_status=player_status_planned,
        )
        booking2 = BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            player_status=player_status_confirmed,
        )

        latest_booking = player_helper.get_latest_booking_for_game(
            self.user_2_per.player, game
        )
        self.assertIsNotNone(latest_booking)
        self.assertEqual(latest_booking, booking2)
        self.assertEqual(latest_booking.player_status, player_status_confirmed)

    def test_get_total_players_for_game(self):
        game = Game.objects.create(
            when="2024-10-01",
            description="total players test game",
            status=Game.PLANNED,
        )
        player_status_confirmed = PlayerStatus.objects.get(player_status="confirmed")
        player_status_planned = PlayerStatus.objects.get(player_status="planned")
        player_status_reserved = PlayerStatus.objects.get(player_status="reserved")

        # Create bookings for different players
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_1_per.player,
            player_status=player_status_confirmed,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            player_status=player_status_planned,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_3_per.player,
            player_status=player_status_reserved,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_4_act.player,
            player_status=player_status_reserved,
        )

        total_players = game_helper.get_total_players_for_game(game)
        # just only 2 confirmed/planned
        self.assertEqual(total_players, 2)

        # add the booking that changes status to cancelled
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            player_status=PlayerStatus.objects.get(player_status="cancelled"),
        )

        # Now total players should be 1 (only user_1_per.player is confirmed)
        total_players = game_helper.get_total_players_for_game(game)
        self.assertEqual(total_players, 1)
