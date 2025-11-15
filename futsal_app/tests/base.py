from django.contrib.auth.models import User
from django.test import Client, TestCase

from games.models import Player


class BaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password123"
        )

        self.user_1_per = User.objects.create_user(username="bolek", password="pass_1")
        self.user_2_per = User.objects.create_user(username="lolek", password="pass_2")
        self.user_3_per = User.objects.create_user(username="tola", password="pass_3")
        self.user_4_act = User.objects.create_user(username="reksio", password="pass_4")

        player_1 = Player.objects.create(
            user=self.user_1_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        player_2 = Player.objects.create(
            user=self.user_2_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        player_3 = Player.objects.create(
            user=self.user_3_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        player_4 = Player.objects.create(
            user=self.user_4_act,
            mobile_number="123456789",
        )  # default role is Active
