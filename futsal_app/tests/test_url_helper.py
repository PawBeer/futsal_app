from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from games.helpers import url_helper


class BuildAbsoluteUrlTests(TestCase):
    def test_uses_request_host_when_request_given(self):
        request = RequestFactory().get("/", SERVER_NAME="testserver")

        url = url_helper.build_absolute_url("/games/confirm/abc/", request=request)

        self.assertEqual(url, "http://testserver/games/confirm/abc/")

    @override_settings(SITE_URL="https://futsal.example.org")
    def test_falls_back_to_site_url_without_request(self):
        url = url_helper.build_absolute_url("/games/confirm/abc/")

        self.assertEqual(url, "https://futsal.example.org/games/confirm/abc/")

    @override_settings(SITE_URL="https://futsal.example.org/")
    def test_tolerates_trailing_slash_in_site_url(self):
        url = url_helper.build_absolute_url("/games/confirm/abc/")

        self.assertEqual(url, "https://futsal.example.org/games/confirm/abc/")

    @override_settings(SITE_URL="https://futsal.example.org")
    def test_request_takes_priority_over_site_url(self):
        request = RequestFactory().get("/", SERVER_NAME="testserver")

        url = url_helper.build_absolute_url("/games/confirm/abc/", request=request)

        self.assertEqual(url, "http://testserver/games/confirm/abc/")


class PasswordResetHostTests(TestCase):
    @override_settings(ALLOWED_HOSTS=["futsal.example.org"])
    def test_password_reset_link_uses_request_host(self):
        # Email links built from a request must use the same host Django's
        # password reset does - this guards against anything (e.g. a fixed
        # SITE_ID) making the reset email ignore the request host.
        User.objects.create_user("bolek", email="bolek@example.com", password="x")

        self.client.post(
            "/accounts/password_reset/",
            {"email": "bolek@example.com"},
            HTTP_HOST="futsal.example.org",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://futsal.example.org/accounts/reset/", mail.outbox[0].body)
