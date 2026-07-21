from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from futsal_app import settings
from games.helpers import player_helper

from .models import PlayerCharge


def send_settlement_email(charge: PlayerCharge) -> None:
    run = charge.settlement_run
    player_display_name = player_helper.get_display_name(charge.player)
    subject = f"Rozliczenie za {run.month:02d}/{run.year}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [charge.player.user.email]

    text_content = (
        f"Hello {player_display_name}, your settlement for {run.month:02d}/{run.year} "
        f"is {charge.amount} for {charge.game_count} game(s)."
    )

    html_content = render_to_string(
        "emails/settlement_email.html",
        {
            "player_display_name": player_display_name,
            "charge": charge,
            "run": run,
        },
    )

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()
