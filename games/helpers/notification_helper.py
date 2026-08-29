from django.urls import reverse
from django.utils import timezone

from games.helpers import game_helper, token_helper, url_helper
from games.mailer import (
    send_standby_availability_email,
    send_weekly_availability_reminder_email,
    send_weekly_game_cancelled_notice_email,
)
from games.models import Game, GameStatus, NotificationType, StatusChoices


def send_standby_availability_reminders(game: Game, request=None) -> int:
    """
    Emails every player currently on the standby list for `game`, inviting
    them to register interest in playing (see mailer.send_standby_availability_email
    for the "not an automatic booking" disclaimer). Shared by the daily
    management command (no request) and the manual "send now" trigger
    (request available - see url_helper.build_absolute_url). Returns how
    many emails were sent.
    """
    standby_players = game_helper.get_players_by_status([StatusChoices.STANDBY], game)

    sent_count = 0
    for player in standby_players:
        if not player.user or not player.user.email:
            continue

        token = token_helper.make_confirm_token(game, player)
        confirm_url = url_helper.build_absolute_url(
            reverse("confirm_participation_url", args=[token]), request=request
        )
        send_standby_availability_email(player, game, confirm_url)
        sent_count += 1

    return sent_count


def send_weekly_reminders_now(game: Game, request=None) -> int:
    """
    Emails every still-Planned player either the "who can't play"
    availability nudge (game still Planned) or the cancellation notice
    (game now Cancelled). Shared by the cron job (no request) and the
    manual "send now" trigger (request available - see
    url_helper.build_absolute_url). Returns how many emails were sent.
    """
    planned_players = game_helper.get_players_by_status([StatusChoices.PLANNED], game)

    sent_count = 0
    for player in planned_players:
        if not player.user or not player.user.email:
            continue

        if game.status == GameStatus.CANCELLED:
            send_weekly_game_cancelled_notice_email(player, game)
        else:
            token = token_helper.make_cancel_token(game, player)
            cancel_url = url_helper.build_absolute_url(
                reverse("cancel_participation_url", args=[token]), request=request
            )
            send_weekly_availability_reminder_email(player, game, cancel_url)
        sent_count += 1

    return sent_count


def send_game_cancelled_notices(game: Game) -> int:
    """
    Emails every player still marked Planned or Confirmed for `game` that it
    has been cancelled. Used by game_status_update to notify them immediately
    instead of waiting for the scheduled weekly reminder. Returns how many
    emails were sent.
    """
    affected_players = game_helper.get_players_by_status(
        [StatusChoices.PLANNED, StatusChoices.CONFIRMED], game
    )

    sent_count = 0
    for player in affected_players:
        if not player.user or not player.user.email:
            continue

        send_weekly_game_cancelled_notice_email(player, game)
        sent_count += 1

    return sent_count


def notify_players_of_cancellation(game: Game) -> int:
    """
    Emails every still-Planned or Confirmed player that `game` was cancelled
    - whether triggered by an admin or by the automatic minimum-players
    check - instead of waiting for the scheduled weekly reminder. Marks the
    weekly reminder as sent so the cron job doesn't email the same Planned
    players again later. Returns how many emails were sent.
    """
    sent_count = send_game_cancelled_notices(game)

    weekly_reminder = game.notifications.filter(
        notification_type=NotificationType.WEEKLY
    ).first()
    if weekly_reminder is not None and weekly_reminder.sent_at is None:
        weekly_reminder.sent_at = timezone.now()
        weekly_reminder.save(update_fields=["sent_at"])

    return sent_count
