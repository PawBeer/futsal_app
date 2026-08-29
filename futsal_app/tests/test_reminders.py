from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.urls import reverse
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


def _make_notification(
    game, notification_type, *, enabled=True, send_at=None, sent_at=None
):
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
        # No request in a management command - the cancel link falls back to
        # the current Site's domain (see games.helpers.url_helper).
        self.assertIn("http://example.com/games/game/cancel/", mail.outbox[0].body)
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
        farther_game = Game.objects.create(
            when=self.farther_game_day, status=GameStatus.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=nearer_game,
            player=self.user_1_per.player,
            status=StatusChoices.PLANNED,
        )
        BookingHistoryForGame.objects.create(
            game=farther_game,
            player=self.user_2_per.player,
            status=StatusChoices.PLANNED,
        )
        _make_notification(
            nearer_game, NotificationType.WEEKLY, send_at=self.past_send_at
        )
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


class SendWeeklyReminderNowViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.game_day = timezone.now().date() + timedelta(days=5)
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

        self.game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=self.game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        self.weekly_reminder = _make_notification(self.game, NotificationType.WEEKLY)
        self.send_now_url = reverse("send_weekly_reminder_url", args=[self.game.id])

    def test_superuser_can_send_reminder_immediately(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.send_now_url)

        self.assertRedirects(response, reverse("game_details_url", args=[self.game.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Who can't play on", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user_1_per.email])
        # Triggered from a view - the cancel link is built from the live
        # request host (Django's test client uses "testserver"), same as
        # request.build_absolute_uri (see games.helpers.url_helper).
        self.assertIn("http://testserver/games/game/cancel/", mail.outbox[0].body)
        self.weekly_reminder.refresh_from_db()
        self.assertIsNotNone(self.weekly_reminder.sent_at)

    def test_sends_cancellation_notice_when_game_is_cancelled(self):
        self.game.status = GameStatus.CANCELLED
        self.game.save()

        self.client.force_login(self.superuser)
        self.client.post(self.send_now_url)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("is cancelled", mail.outbox[0].subject)

    def test_non_superuser_cannot_trigger_reminder(self):
        self.client.force_login(self.user_1_per)
        self.client.post(self.send_now_url)

        self.assertEqual(len(mail.outbox), 0)
        self.weekly_reminder.refresh_from_db()
        self.assertIsNone(self.weekly_reminder.sent_at)


class ImmediateCancellationNoticeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.game_day = timezone.now().date() + timedelta(days=5)
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

        self.game = Game.objects.create(when=self.game_day, status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=self.game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_2_per.player,
            status=StatusChoices.CONFIRMED,
        )
        self.status_update_url = reverse("game_status_update_url", args=[self.game.id])

    def test_cancelling_notifies_planned_and_confirmed_players_immediately(self):
        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.CANCELLED})

        self.assertEqual(len(mail.outbox), 2)
        recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(recipients, {self.user_1_per.email, self.user_2_per.email})
        self.assertIn("is cancelled", mail.outbox[0].subject)

    def test_recancelling_an_already_cancelled_game_sends_nothing(self):
        self.game.status = GameStatus.CANCELLED
        self.game.save()

        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.CANCELLED})

        self.assertEqual(len(mail.outbox), 0)

    def test_no_notice_when_game_notifications_disabled(self):
        self.game.notifications_enabled = False
        self.game.save()

        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.CANCELLED})

        self.assertEqual(len(mail.outbox), 0)

    def test_cancelling_marks_weekly_reminder_as_sent_to_avoid_duplicate_cron_send(
        self,
    ):
        weekly_reminder = _make_notification(
            self.game, NotificationType.WEEKLY, send_at=timezone.now()
        )

        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.CANCELLED})

        weekly_reminder.refresh_from_db()
        self.assertIsNotNone(weekly_reminder.sent_at)

    def test_missing_weekly_reminder_does_not_crash(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self.status_update_url, {"status": GameStatus.CANCELLED}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)


class CheckMinimumPlayersTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.past_send_at = timezone.now() - timedelta(hours=1)
        self.future_send_at = timezone.now() + timedelta(days=1)
        self.game_day = timezone.now().date() + timedelta(days=5)
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

    def test_cancels_and_notifies_when_below_threshold(self):
        game = Game.objects.create(
            when=self.game_day, status=GameStatus.PLANNED, minimum_players=2
        )
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        check = _make_notification(
            game, NotificationType.MIN_PLAYERS_CHECK, send_at=self.past_send_at
        )

        call_command("check_minimum_players")

        game.refresh_from_db()
        self.assertEqual(game.status, GameStatus.CANCELLED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("is cancelled", mail.outbox[0].subject)
        check.refresh_from_db()
        self.assertIsNotNone(check.sent_at)

    def test_counts_planned_and_confirmed_towards_threshold(self):
        game = Game.objects.create(
            when=self.game_day, status=GameStatus.PLANNED, minimum_players=2
        )
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_2_per.player, status=StatusChoices.CONFIRMED
        )
        _make_notification(
            game, NotificationType.MIN_PLAYERS_CHECK, send_at=self.past_send_at
        )

        call_command("check_minimum_players")

        game.refresh_from_db()
        self.assertEqual(game.status, GameStatus.PLANNED)
        self.assertEqual(len(mail.outbox), 0)

    def test_not_yet_due_is_skipped(self):
        game = Game.objects.create(
            when=self.game_day, status=GameStatus.PLANNED, minimum_players=2
        )
        _make_notification(
            game, NotificationType.MIN_PLAYERS_CHECK, send_at=self.future_send_at
        )

        call_command("check_minimum_players")

        game.refresh_from_db()
        self.assertEqual(game.status, GameStatus.PLANNED)
        self.assertEqual(len(mail.outbox), 0)

    def test_already_checked_is_not_rechecked(self):
        game = Game.objects.create(
            when=self.game_day, status=GameStatus.PLANNED, minimum_players=2
        )
        _make_notification(
            game,
            NotificationType.MIN_PLAYERS_CHECK,
            send_at=self.past_send_at,
            sent_at=timezone.now(),
        )

        call_command("check_minimum_players")

        game.refresh_from_db()
        self.assertEqual(game.status, GameStatus.PLANNED)
        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_check_is_skipped(self):
        game = Game.objects.create(
            when=self.game_day, status=GameStatus.PLANNED, minimum_players=2
        )
        _make_notification(
            game,
            NotificationType.MIN_PLAYERS_CHECK,
            enabled=False,
            send_at=self.past_send_at,
        )

        call_command("check_minimum_players")

        game.refresh_from_db()
        self.assertEqual(game.status, GameStatus.PLANNED)
        self.assertEqual(len(mail.outbox), 0)


class MinimumPlayersFormTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.game = Game.objects.create(
            when=timezone.now().date() + timedelta(days=5),
            status=GameStatus.PLANNED,
            minimum_players=8,
        )
        self.check = _make_notification(self.game, NotificationType.MIN_PLAYERS_CHECK)
        self.status_update_url = reverse("game_status_update_url", args=[self.game.id])

    def test_superuser_can_update_minimum_players_and_check_time(self):
        self.client.force_login(self.superuser)
        new_send_at = timezone.now() + timedelta(days=3)
        self.client.post(
            self.status_update_url,
            {
                "status": GameStatus.PLANNED,
                "min_players_check_enabled_submitted": "1",
                "min_players_check_enabled": "on",
                "min_players_check_send_at": new_send_at.strftime("%Y-%m-%dT%H:%M"),
                "minimum_players": "5",
            },
        )

        self.game.refresh_from_db()
        self.check.refresh_from_db()
        self.assertEqual(self.game.minimum_players, 5)
        self.assertTrue(self.check.enabled)
        self.assertEqual(
            self.check.send_at.strftime("%Y-%m-%dT%H:%M"),
            new_send_at.strftime("%Y-%m-%dT%H:%M"),
        )

    def test_non_superuser_cannot_update_minimum_players(self):
        self.client.force_login(self.user_1_per)
        self.client.post(
            self.status_update_url,
            {"status": GameStatus.PLANNED, "minimum_players": "5"},
        )

        self.game.refresh_from_db()
        self.assertEqual(self.game.minimum_players, 8)
