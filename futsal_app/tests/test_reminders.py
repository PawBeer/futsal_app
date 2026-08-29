from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from games.models import (
    BookingHistoryForGame,
    Game,
    GameNotification,
    GameStatus,
    NotificationType,
    StatusChoices,
)

from .base import BaseTestCase


def _make_notification(game, notification_type, *, enabled=True, send_at=None, sent_at=None):
    return GameNotification.objects.create(
        game=game,
        notification_type=notification_type,
        enabled=enabled,
        send_at=send_at,
        sent_at=sent_at,
    )


class SendWeeklyRemindersTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.past_send_at = timezone.now() - timedelta(hours=1)
        self.future_send_at = timezone.now() + timedelta(days=1)
        self.game_day = timezone.now().date() + timedelta(days=5)
        self.farther_game_day = timezone.now().date() + timedelta(days=12)
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

    def test_sends_availability_reminder_for_due_planned_game(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        notification = _make_notification(
            game, NotificationType.WEEKLY, send_at=self.past_send_at
        )

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Who can't play on", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user_1_per.email])
        notification.refresh_from_db()
        self.assertIsNotNone(notification.sent_at)

    def test_sends_cancellation_notice_for_due_cancelled_game(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.CANCELLED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        _make_notification(game, NotificationType.WEEKLY, send_at=self.past_send_at)

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("is cancelled", mail.outbox[0].subject)

    def test_already_sent_is_not_resent(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        _make_notification(
            game,
            NotificationType.WEEKLY,
            send_at=self.past_send_at,
            sent_at=timezone.now(),
        )

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_reminder_is_skipped(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        _make_notification(
            game, NotificationType.WEEKLY, enabled=False, send_at=self.past_send_at
        )

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 0)

    def test_not_yet_due_is_skipped(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        _make_notification(game, NotificationType.WEEKLY, send_at=self.future_send_at)

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 0)

    def test_only_nearest_due_game_is_processed(self):
        nearer_game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        farther_game = Game.objects.create(when=self.farther_game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=nearer_game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=farther_game, player=self.user_2_per.player, status=StatusChoices.PLANNED
        )
        _make_notification(nearer_game, NotificationType.WEEKLY, send_at=self.past_send_at)
        farther_notification = _make_notification(
            farther_game, NotificationType.WEEKLY, send_at=self.past_send_at
        )

        call_command("send_weekly_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_1_per.email])
        farther_notification.refresh_from_db()
        self.assertIsNone(farther_notification.sent_at)


class SendStandbyRemindersTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.past_send_at = timezone.now() - timedelta(hours=1)
        self.game_day = timezone.now().date() + timedelta(days=5)
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

    def test_sends_invite_to_standby_players(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.STANDBY
        )
        notification = _make_notification(
            game, NotificationType.STANDBY, send_at=self.past_send_at
        )

        call_command("send_standby_reminders")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Want to play on", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user_1_per.email])
        notification.refresh_from_db()
        self.assertIsNotNone(notification.sent_at)

    def test_already_sent_is_not_resent(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.STANDBY
        )
        _make_notification(
            game,
            NotificationType.STANDBY,
            send_at=self.past_send_at,
            sent_at=timezone.now(),
        )

        call_command("send_standby_reminders")

        self.assertEqual(len(mail.outbox), 0)

    def test_cancelled_game_is_not_eligible(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.CANCELLED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.STANDBY
        )
        _make_notification(game, NotificationType.STANDBY, send_at=self.past_send_at)

        call_command("send_standby_reminders")

        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_reminder_is_skipped(self):
        game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.STANDBY
        )
        _make_notification(
            game, NotificationType.STANDBY, enabled=False, send_at=self.past_send_at
        )

        call_command("send_standby_reminders")

        self.assertEqual(len(mail.outbox), 0)
