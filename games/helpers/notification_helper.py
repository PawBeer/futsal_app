from django.conf import settings
from django.urls import reverse

from games.helpers import game_helper, token_helper
from games.mailer import send_standby_availability_email
from games.models import Game, StatusChoices


def send_standby_availability_reminders(game: Game) -> int:
    """
    Emails every player currently on the standby list for `game`, inviting
    them to register interest in playing (see mailer.send_standby_availability_email
    for the "not an automatic booking" disclaimer). Shared by the daily
    management command and the manual "send now" trigger. Returns how many
    emails were sent.
    """
    standby_players = game_helper.get_players_by_status([StatusChoices.STANDBY], game)

    sent_count = 0
    for player in standby_players:
        if not player.user or not player.user.email:
            continue

        token = token_helper.make_confirm_token(game, player)
        confirm_url = settings.SITE_URL + reverse(
            "confirm_participation_url", args=[token]
        )
        send_standby_availability_email(player, game, confirm_url)
        sent_count += 1

    return sent_count
