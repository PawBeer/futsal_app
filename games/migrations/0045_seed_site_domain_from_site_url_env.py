import os
from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def seed_site_domain_from_site_url_env(apps, schema_editor):
    """
    One-time bridge for existing deployments: SITE_URL used to be the only
    source of the app's public host. Now that's the Site row's domain
    (SITE_ID, editable at /admin/sites/site/), so seed it from the old env
    var if one was set, instead of leaving the Django default
    "example.com".
    """
    site_url = os.environ.get("SITE_URL")
    if not site_url:
        return

    domain = urlparse(site_url).netloc
    if not domain:
        return

    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=getattr(settings, "SITE_ID", 1),
        defaults={"domain": domain, "name": domain},
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0044_backfill_min_players_check_notifications"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(seed_site_domain_from_site_url_env, noop_reverse),
    ]
