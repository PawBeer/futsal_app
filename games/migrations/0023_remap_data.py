from django.db import migrations


def rename_keys(apps, schema_editor):
    games_model = apps.get_model("games", "BookingHistoryForGame")

    # Mapowanie starych wartości na nowe
    mapping = {
        1: "planned",
        2: "cancelled",
        3: "reserved",
        4: "confirmed",
    }

    for old_value, new_value in mapping.items():
        games_model.objects.filter(status=old_value).update(status=new_value)


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0022_rename_playerstatusmanager_playerstatus_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_keys),
    ]
