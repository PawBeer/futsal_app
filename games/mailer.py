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
    player_display_name = player_helper.get_display_name(player)
    # Fallback plain text version
    text_content = f"Hello {player_display_name}, there is an update regarding Game on {game.when}. Please check your account for details."

    # Render the template with context
    html_content = render_to_string(
        "emails/player_status_update.html",
        {
            "player_display_name": player_display_name,
            "game": game,
            "status": status,
        },
    )

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_player_status_update_email_to_admins(player: Player, game: Game, status: str):
    """
    Send an email notification to all admin users when a player changes their status for a game.

    This function composes a plain-text fallback message and an HTML message rendered from the
    "emails/player_status_update_for_admin.html" template, filling the template context with:
    - player_display_name: display name for the player (via player_helper.get_display_name)
    - game: the Game instance
    - status: the new status string
    - no_players: total players for the game (via game_helper.get_total_players_for_game)

    For each superuser (User.objects.filter(is_superuser=True)) an individual EmailMultiAlternatives
    message is created and sent to the admin.email address using settings.DEFAULT_FROM_EMAIL as the
    sender. The subject is set to "The status change for the player".

    Parameters:
        player (Player): The player whose status changed.
        game (Game): The game for which the status change occurred.
        status (str): The new status value (e.g., "confirmed", "declined", "tentative").

    Returns:
        None

    Side effects:
        - Sends one email per admin user (synchronous I/O).
        - Renders a template to produce HTML content.
        - May produce log entries or exceptions from the email backend or template system.

    Notes / Potential failure modes:
        - If the template is missing, render_to_string may raise TemplateDoesNotExist.
        - Email delivery may fail and raise smtplib.SMTPException or backend-specific exceptions.
        - Admin users without an email address will receive an email to an empty recipient list (behavior depends on email backend).
        - The function currently iterates and sends emails synchronously; consider delegating to a background task
          to avoid blocking request handling and to better handle retries.
        - There is a comment indicating a preference check ("check if admin wants to receive such emails") but
          no implementation: implement admin notification preferences if required.

    Dependencies:
        - Django template rendering (render_to_string)
        - django.contrib.auth.models.User
        - django.core.mail.EmailMultiAlternatives
        - settings.DEFAULT_FROM_EMAIL
        - player_helper and game_helper utilities used for display name and player counts.
    """

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
