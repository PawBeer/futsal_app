from games.helpers import game_helper, player_helper
from games.models import (
    BookingHistoryForGame,
    Game,
    GameStatus,
    StatusChoices,
)

from .base import BaseTestCase


class BookingModelTests(BaseTestCase):

    def test_booking_creation(self):

        game = Game.objects.create(
            when="2024-08-01",
            description="booking test game",
            status=GameStatus.PLANNED,
        )
        player_status = StatusChoices.PLANNED
        booking = BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_1_per.player,
            status=player_status,
        )
        self.assertEqual(BookingHistoryForGame.objects.count(), 1)
        self.assertEqual(booking.player, self.user_1_per.player)
        self.assertEqual(booking.game, game)
        self.assertEqual(booking.status, player_status)

    def test_get_latest_booking_for_game(self):
        game = Game.objects.create(
            when="2024-09-01",
            description="latest booking test game",
            status=GameStatus.PLANNED,
        )

        # Create two bookings for the same player and game
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            status=StatusChoices.PLANNED,
        )
        booking2 = BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            status=StatusChoices.CONFIRMED,
        )

        latest_booking = player_helper.get_latest_booking_for_game(
            self.user_2_per.player, game
        )
        self.assertIsNotNone(latest_booking)
        self.assertEqual(latest_booking, booking2)
        self.assertEqual(latest_booking.status, StatusChoices.CONFIRMED)

    def test_get_total_players_for_game(self):
        game = Game.objects.create(
            when="2024-10-01",
            description="total players test game",
            status=GameStatus.PLANNED,
        )

        # Create bookings for different players
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_1_per.player,
            status=StatusChoices.CONFIRMED,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            status=StatusChoices.PLANNED,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_3_per.player,
            status=StatusChoices.RESERVED,
        )
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_4_act.player,
            status=StatusChoices.RESERVED,
        )

        total_players = game_helper.get_total_players_for_game(game)
        # just only 2 confirmed/planned
        self.assertEqual(total_players, 2)

        # add the booking that changes status to cancelled
        BookingHistoryForGame.objects.create(
            game=game,
            player=self.user_2_per.player,
            status=StatusChoices.CANCELLED,  # @fixme
        )

        # Now total players should be 1 (only user_1_per.player is confirmed)
        total_players = game_helper.get_total_players_for_game(game)
        self.assertEqual(total_players, 1)
