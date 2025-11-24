from unittest.mock import patch

from django.urls import reverse

from games.models import Player

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
