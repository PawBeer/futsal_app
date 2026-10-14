from django.conf import settings


def build_absolute_url(path: str, request=None) -> str:
    """
    Builds an absolute URL for `path`, the same way Django's own password
    reset flow determines its host: from the live request when one is
    available (request.build_absolute_uri - the scheme and host Django's
    get_current_site/RequestSite and request.is_secure() report there).

    Code that runs outside a request/response cycle - such as a management
    command polled by cron - has no request to read the host from, so it
    falls back to settings.SITE_URL.
    """
    if request is not None:
        return request.build_absolute_uri(path)

    return settings.SITE_URL.rstrip("/") + path
