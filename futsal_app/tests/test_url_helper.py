from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase, override_settings

from games.helpers import url_helper


class BuildAbsoluteUrlTests(TestCase):
    def setUp(self):
        super().setUp()
        # Site.objects.get_current() caches results at the module level,
        # independent of the DB transaction rollback between tests.
        self.addCleanup(Site.objects.clear_cache)

    def test_uses_request_host_when_request_given(self):
        request = RequestFactory().get("/", SERVER_NAME="testserver")

        url = url_helper.build_absolute_url("/games/confirm/abc/", request=request)

        self.assertEqual(url, "http://testserver/games/confirm/abc/")

    def test_falls_back_to_current_site_domain_without_request(self):
        site = Site.objects.get(pk=1)
        site.domain = "futsal.example.org"
        site.save()

        url = url_helper.build_absolute_url("/games/confirm/abc/")

        self.assertEqual(url, "http://futsal.example.org/games/confirm/abc/")

    @override_settings(SITE_USE_HTTPS=True)
    def test_uses_https_scheme_when_configured(self):
        site = Site.objects.get(pk=1)
        site.domain = "futsal.example.org"
        site.save()

        url = url_helper.build_absolute_url("/games/confirm/abc/")

        self.assertEqual(url, "https://futsal.example.org/games/confirm/abc/")

    def test_request_takes_priority_over_site_domain(self):
        site = Site.objects.get(pk=1)
        site.domain = "futsal.example.org"
        site.save()
        request = RequestFactory().get("/", SERVER_NAME="testserver")

        url = url_helper.build_absolute_url("/games/confirm/abc/", request=request)

        self.assertEqual(url, "http://testserver/games/confirm/abc/")
