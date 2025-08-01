# Generated by Django 5.2.3 on 2025-07-23 07:12

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0006_player_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookinghistoryforgame',
            name='creation_date',
            field=models.DateField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='bookinghistoryforgame',
            name='updated_date',
            field=models.DateField(auto_now=True),
        ),
    ]
