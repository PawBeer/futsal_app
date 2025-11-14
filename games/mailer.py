from django.core.mail import send_mail

from futsal_app import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.models import User

from games.helpers import game_helper, player_helper
from games.models import Game, Player


def send_welcome_email(user, activation_link):
    subject = "Welcome to our site!"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [user.email]

    # Render the template with context
    html_content = render_to_string(
        "emails/welcome.html",
        {
            "user": user,
            "activation_link": activation_link,
        },
    )

    # Fallback plain text version
    text_content = "Hello {}, welcome! Visit this link to activate: {}".format(
        user.username, activation_link
    )

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_game_update_email(user, game, update_type):
    subject = f"Update on Game {game.id}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [user.email]

    # Render the template with context
    html_content = render_to_string(
        "emails/game_update.html",
        {
            "user": user,
            "game": game,
            "update_type": update_type,
        },
    )

    # Fallback plain text version
    text_content = f"Hello {user.username}, there is an update regarding Game {game.id}. Please check your account for details."

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_player_status_update_email(player: Player, game, status: str):
    subject = "Your Futsal Player Status Has Been Updated"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [player.user.email]

    # Fallback plain text version
    text_content = f"Hello {player.user.username}, there is an update regarding Game on {game.when}. Please check your account for details."

    # Render the template with context
    html_content = render_to_string(
        "emails/player_status_update.html",
        {
            "user": player.user,
            "game": game,
            "status": status,
        },
    )

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_player_status_update_email_to_admins(player: Player, game: Game, status: str):

    # Fallback plain text version
    text_content = f"For the game on {game.when} the player {player_helper.get_display_name(player)} changed status to {status}."

    # Render the template with context
    html_content = render_to_string(
        "emails/player_status_update_for_admin.html",
        {
            "player_display_name": player_helper.get_display_name(player),
            "game": game,
            "status": status,
            "no_players": game_helper.get_total_players_for_game(game),
        },
    )
    subject = "The status change for the player"
    from_email = settings.DEFAULT_FROM_EMAIL
    admins = User.objects.filter(is_superuser=True)
    for admin in admins:
        # feature: check if admin wants to receive such emails
        to = [admin.email]
        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
