from games.models import Player

from .base import BaseTestCase
from unittest.mock import patch
from django.urls import reverse


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
