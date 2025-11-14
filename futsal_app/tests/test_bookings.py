from games.helpers import player_helper
from .base import BaseTestCase
from games.models import BookingHistoryForGame, Game, PlayerStatus
from games.helpers import game_helper


class BookingModelTests(BaseTestCase):

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
        booking1 = BookingHistoryForGame.objects.create(
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
