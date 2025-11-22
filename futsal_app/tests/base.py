from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from games.models import Player

User = get_user_model()


class BaseTestCase(TestCase):
    """
    BaseTestCase sets up a common test fixture for futsal_app tests.

    It initializes:
    - self.client: Django test Client instance for simulating HTTP requests.
    - self.superuser: a created superuser with credentials:
        username="admin", password="password123"
      (email set to "admin@example.com").
    - Four regular User instances with corresponding Player records:
        1. username="bolek"  (password="pass_1")  -> Player with ROLE_PERMANENT
        2. username="lolek"  (password="pass_2")  -> Player with ROLE_PERMANENT
        3. username="tola"   (password="pass_3")  -> Player with ROLE_PERMANENT
        4. username="reksio" (password="pass_4")  -> Player with default role (Active)

    All Player.mobile_number values are set to a placeholder "123456789".

    Attributes available in tests:
    - client: django.test.Client
    - superuser: auth.User (superuser)
    - user_1_per, user_2_per, user_3_per, user_4_act: auth.User
    - corresponding Player instances (accessible via Player.objects.get(user=...))

    Notes:
    - Passwords here are plaintext for test login convenience; use Django's test client
      login methods (client.login) if authentication is required in tests.
    - The permanent/active roles are set to exercise permission- or role-based logic
      in test cases.
    """

    def setUp(self):
        self.client = Client()

        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password123"
        )

        self.user_1_per = User.objects.create_user(username="bolek", password="pass_1")
        self.user_2_per = User.objects.create_user(username="lolek", password="pass_2")
        self.user_3_per = User.objects.create_user(username="tola", password="pass_3")
        self.user_4_act = User.objects.create_user(username="reksio", password="pass_4")

        Player.objects.create(
            user=self.user_1_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        Player.objects.create(
            user=self.user_2_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        Player.objects.create(
            user=self.user_3_per,
            mobile_number="123456789",
            role=Player.ROLE_PERMANENT,
        )
        Player.objects.create(
            user=self.user_4_act,
            mobile_number="123456789",
        )  # default role is Active
