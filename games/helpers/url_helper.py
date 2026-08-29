from django.conf import settings
from django.contrib.sites.models import Site


def build_absolute_url(path: str, request=None) -> str:
    """
    Builds an absolute URL for `path`, the same way Django's own password
    reset flow determines its host: from the live request when one is
    available (see request.build_absolute_uri, used by
    django.contrib.auth.views.PasswordResetView via get_current_site).

    Code that runs outside a request/response cycle - such as a management
    command polled by cron - has no request to read the host from, so it
    falls back to the current Site's domain (SITE_ID), configurable at
    /admin/sites/site/ instead of a hardcoded setting.
    """
    if request is not None:
        return request.build_absolute_uri(path)

    site = Site.objects.get_current()
    scheme = "https" if settings.SITE_USE_HTTPS else "http"
    return f"{scheme}://{site.domain}{path}"
