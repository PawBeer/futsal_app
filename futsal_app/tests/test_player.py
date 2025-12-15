from unittest.mock import patch

from django.urls import reverse

from games.helpers.game_helper import get_players_by_status
from games.models import BookingHistoryForGame, Game, Player, PlayerStatus

from .base import BaseTestCase


class PlayerModelTests(BaseTestCase):

    def test_players_various_roles(self):

        self.assertEqual(Player.objects.all().count(), 4)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_PERMANENT).count(), 3)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_INACTIVE).count(), 0)
        self.assertEqual(Player.objects.filter(role=Player.ROLE_ACTIVE).count(), 1)

    @patch("games.views.send_welcome_email")
    def test_player_details_send_welcome_email(self, mock_send_welcome_email):
        data = {
            "form_type": "welcome_email",
        }
        reksio = Player.objects.get(user__username="reksio")
        self.client.force_login(self.superuser)
        url = reverse("player_details_url", kwargs={"player_id": reksio.id})
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, url)
        mock_send_welcome_email.assert_called_once()

    def test_add_player_view(self):
        data = {
            "username": "newplayer",
            "first_name": "New",
            "last_name": "Player",
            "email": "player@example.com",
            "mobile_number": "123456789",
            "role": Player.ROLE_ACTIVE,
        }
        self.client.force_login(self.superuser)
        url = reverse("add_player_url")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        new_player = Player.objects.get(user__username="newplayer")
        self.assertIsNotNone(new_player)
        self.assertEqual(new_player.mobile_number, "123456789")
        self.assertEqual(new_player.role, Player.ROLE_ACTIVE)

    def test_update_player_view(self):
        tola = Player.objects.get(user__username="tola")
        data = {
            "form_type": "profile",  # fixme: currently the same url handles 2 posts distinguished by form_type
            "username": tola.user.username,  # username is not changed
            "email": tola.user.email,  # email is not changed
            "mobile_number": "987654321",  # tola's current is "123456789"
            "role": Player.ROLE_INACTIVE,  # changing from Permanent to Inactive
        }
        self.client.force_login(self.superuser)
        url = reverse("player_details_url", kwargs={"player_id": tola.id})
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        updated_tola = Player.objects.get(user__username="tola")
        self.assertEqual(updated_tola.mobile_number, "987654321")
        self.assertEqual(updated_tola.role, Player.ROLE_INACTIVE)

    def _create_user_and_player(self, username: str, role: str) -> Player:
        from django.contrib.auth.models import User

        user = User.objects.create_user(username=username, password="testpass")
        player = Player.objects.create(user=user, role=role)
        return player

    def _change_player_status_for_game(
        self, player: Player, game: Game, new_status: str
    ):

        BookingHistoryForGame.objects.create(
            player=player,
            game_id=game.id,
            status=new_status,
        )

    def test_awaiting_players_are_picked_in_fifo_order(self):

        new_player1 = self._create_user_and_player(
            "some_new_player_1", Player.ROLE_ACTIVE
        )
        game = Game.objects.create(
            when="2024-07-01", description="just a test game", status=Game.PLANNED
        )
        # we should have now 3 planned and 2 reserved player

        reksio = Player.objects.get(user__username="reksio")

        self._change_player_status_for_game(reksio, game, PlayerStatus.AWAITING)
        self._change_player_status_for_game(new_player1, game, PlayerStatus.AWAITING)

        awaiting_players = get_players_by_status([PlayerStatus.AWAITING], game)
        self.assertEqual(len(awaiting_players), 2)
        self.assertEqual(awaiting_players[0], reksio)
        self.assertEqual(awaiting_players[1], new_player1)

        awaiting_players = get_players_by_status(
            [PlayerStatus.AWAITING], game, order_by="-latest_creation_date"
        )
        self.assertEqual(len(awaiting_players), 2)
        self.assertEqual(awaiting_players[1], reksio)
        self.assertEqual(awaiting_players[0], new_player1)
