from datetime import date
from decimal import Decimal

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from games.helpers import settlement_helper
from games.models import (
    BookingHistoryForGame,
    Game,
    GamePrice,
    GameStatus,
    SettlementRun,
    StatusChoices,
    SubstitutePayment,
)

from .base import BaseTestCase


class SettlementCalculationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.price = GamePrice.objects.create(
            amount=Decimal("20.00"), valid_from=date(2026, 1, 1)
        )

    def test_played_game_with_planned_status_is_charged(self):
        game = Game.objects.create(when=date(2026, 3, 5), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].player, self.user_1_per.player)
        self.assertEqual(settlements[0].total, Decimal("20.00"))
        self.assertEqual(settlements[0].game_count, 1)

    def test_cancelled_game_with_cancelled_status_is_charged(self):
        game = Game.objects.create(when=date(2026, 3, 6), status=GameStatus.CANCELLED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.CANCELLED
        )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].total, Decimal("20.00"))

    def test_game_still_planned_is_excluded_entirely(self):
        game = Game.objects.create(when=date(2026, 3, 7), status=GameStatus.PLANNED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(settlements, [])

    def test_non_chargeable_player_statuses_are_excluded(self):
        for status in [
            StatusChoices.CONFIRMED,
            StatusChoices.RESTING,
            StatusChoices.STANDBY,
            StatusChoices.AWAITING,
        ]:
            with self.subTest(status=status):
                game = Game.objects.create(
                    when=date(2026, 3, 8), status=GameStatus.PLAYED
                )
                BookingHistoryForGame.objects.create(
                    game=game, player=self.user_1_per.player, status=status
                )

                settlements = settlement_helper.calculate_settlement(2026, 3)

                self.assertEqual(settlements, [])

    def test_price_change_mid_period_bills_each_game_at_its_own_price(self):
        GamePrice.objects.create(amount=Decimal("25.00"), valid_from=date(2026, 3, 15))
        game_before = Game.objects.create(
            when=date(2026, 3, 10), status=GameStatus.PLAYED
        )
        game_after = Game.objects.create(
            when=date(2026, 3, 20), status=GameStatus.PLAYED
        )
        for game in (game_before, game_after):
            BookingHistoryForGame.objects.create(
                game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
            )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].total, Decimal("45.00"))
        self.assertEqual(settlements[0].game_count, 2)

    def test_multiple_qualifying_games_are_summed(self):
        game_1 = Game.objects.create(when=date(2026, 3, 3), status=GameStatus.PLAYED)
        game_2 = Game.objects.create(
            when=date(2026, 3, 17), status=GameStatus.CANCELLED
        )
        BookingHistoryForGame.objects.create(
            game=game_1, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=game_2, player=self.user_1_per.player, status=StatusChoices.CANCELLED
        )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0].total, Decimal("40.00"))
        self.assertEqual(settlements[0].game_count, 2)

    def test_games_outside_period_are_excluded(self):
        game = Game.objects.create(when=date(2026, 2, 28), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        settlements = settlement_helper.calculate_settlement(2026, 3)

        self.assertEqual(settlements, [])

    def test_game_missing_price_is_flagged_and_billed_as_zero(self):
        # game predates the only configured price
        game = Game.objects.create(when=date(2025, 12, 15), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        settlements = settlement_helper.calculate_settlement(2025, 12)
        missing = settlement_helper.games_missing_price(2025, 12)

        self.assertEqual(settlements[0].total, Decimal("0.00"))
        self.assertEqual(missing, [game])


class SettlementPersistenceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))

    def test_persist_creates_run_and_charges(self):
        game = Game.objects.create(when=date(2026, 4, 5), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        run = settlement_helper.persist_settlement(2026, 4)

        self.assertEqual(run.year, 2026)
        self.assertEqual(run.month, 4)
        self.assertEqual(run.charges.count(), 1)
        charge = run.charges.first()
        self.assertEqual(charge.player, self.user_1_per.player)
        self.assertEqual(charge.amount, Decimal("20.00"))
        self.assertEqual(charge.game_count, 1)
        self.assertFalse(charge.is_paid)

    def test_resend_preserves_paid_status_but_updates_amount(self):
        game = Game.objects.create(when=date(2026, 4, 5), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        run = settlement_helper.persist_settlement(2026, 4)
        charge = run.charges.first()
        charge.is_paid = True
        charge.paid_at = timezone.now()
        charge.marked_by = self.superuser
        charge.save()

        game_2 = Game.objects.create(when=date(2026, 4, 12), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game_2, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )

        run_again = settlement_helper.persist_settlement(2026, 4)

        self.assertEqual(run_again.id, run.id)
        self.assertEqual(SettlementRun.objects.count(), 1)
        charge.refresh_from_db()
        self.assertTrue(charge.is_paid)
        self.assertIsNotNone(charge.paid_at)
        self.assertEqual(charge.marked_by, self.superuser)
        self.assertEqual(charge.amount, Decimal("40.00"))
        self.assertEqual(charge.game_count, 2)


class PermissionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.accountant = self.user_1_per.player
        self.accountant.is_accountant = True
        self.accountant.save()
        self.overview_url = reverse("settlement_overview_url")
        self.send_url = reverse("send_settlement_url")
        self.who_paid_url = reverse("who_paid_url")

    def test_anonymous_user_is_redirected_from_overview(self):
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, 302)

    def test_non_accountant_non_superuser_is_denied_overview(self):
        self.client.force_login(self.user_4_act)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, 302)

    def test_accountant_can_access_overview(self):
        self.client.force_login(self.user_1_per)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_without_player_row_can_access_overview(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, 200)

    def test_any_authenticated_user_can_view_who_paid(self):
        self.client.force_login(self.user_4_act)
        response = self.client.get(self.who_paid_url)
        self.assertEqual(response.status_code, 200)

    def test_non_accountant_cannot_send_settlement(self):
        self.client.force_login(self.user_4_act)
        response = self.client.post(self.send_url, {"year": 2026, "month": 3})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SettlementRun.objects.count(), 0)


class ToggleAndWhoPaidViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))
        self.accountant = self.user_1_per.player
        self.accountant.is_accountant = True
        self.accountant.save()

        game = Game.objects.create(when=date(2026, 5, 5), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_2_per.player, status=StatusChoices.PLANNED
        )
        self.run = settlement_helper.persist_settlement(2026, 5)
        self.charge = self.run.charges.first()

    def test_toggle_marks_charge_paid(self):
        self.client.force_login(self.user_1_per)
        response = self.client.post(
            reverse("toggle_paid_url", args=[self.charge.id]),
            {"year": 2026, "month": 5},
        )
        self.assertEqual(response.status_code, 302)
        self.charge.refresh_from_db()
        self.assertTrue(self.charge.is_paid)
        self.assertIsNotNone(self.charge.paid_at)
        self.assertEqual(self.charge.marked_by, self.user_1_per)

    def test_toggle_again_marks_charge_unpaid(self):
        self.client.force_login(self.user_1_per)
        toggle_url = reverse("toggle_paid_url", args=[self.charge.id])
        self.client.post(toggle_url, {"year": 2026, "month": 5})
        self.client.post(toggle_url, {"year": 2026, "month": 5})

        self.charge.refresh_from_db()
        self.assertFalse(self.charge.is_paid)
        self.assertIsNone(self.charge.paid_at)

    def test_who_paid_reflects_db_state(self):
        self.charge.is_paid = True
        self.charge.save()

        self.client.force_login(self.user_4_act)
        response = self.client.get(reverse("who_paid_url"), {"year": 2026, "month": 5})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paid")

    def test_who_paid_empty_state_does_not_error(self):
        self.client.force_login(self.user_4_act)
        response = self.client.get(reverse("who_paid_url"), {"year": 2099, "month": 1})
        self.assertEqual(response.status_code, 200)


class SettlementEmailSendingTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))
        self.accountant = self.user_1_per.player
        self.accountant.is_accountant = True
        self.accountant.save()
        for user in (self.user_1_per, self.user_2_per, self.user_3_per):
            user.email = f"{user.username}@example.com"
            user.save()

        game = Game.objects.create(when=date(2026, 6, 5), status=GameStatus.PLAYED)
        # user_1 and user_2 qualify, user_3 does not (resting)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_1_per.player, status=StatusChoices.PLANNED
        )
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_2_per.player, status=StatusChoices.CANCELLED
        )
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_3_per.player, status=StatusChoices.RESTING
        )
        self.send_url = reverse("send_settlement_url")

    def test_send_emails_only_qualifying_players(self):
        self.client.force_login(self.user_1_per)
        self.client.post(self.send_url, {"year": 2026, "month": 6})

        self.assertEqual(len(mail.outbox), 2)
        recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(recipients, {self.user_1_per.email, self.user_2_per.email})

    def test_send_emails_skips_already_paid_players(self):
        run = settlement_helper.persist_settlement(2026, 6)
        charge = run.charges.get(player=self.user_1_per.player)
        charge.is_paid = True
        charge.save()

        self.client.force_login(self.user_1_per)
        self.client.post(self.send_url, {"year": 2026, "month": 6})

        self.assertEqual(len(mail.outbox), 1)
        recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(recipients, {self.user_2_per.email})

    def test_resend_grows_outbox_and_increments_send_count(self):
        self.client.force_login(self.user_1_per)
        self.client.post(self.send_url, {"year": 2026, "month": 6})
        self.client.post(self.send_url, {"year": 2026, "month": 6})

        self.assertEqual(len(mail.outbox), 4)
        run = SettlementRun.objects.get(year=2026, month=6)
        self.assertEqual(run.send_count, 2)
        self.assertIsNotNone(run.last_sent_at)


class SubstitutePaymentEmailTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))
        for user in (self.user_1_per, self.user_2_per, self.user_3_per):
            user.email = f"{user.username}@example.com"
            user.save()

        self.game = Game.objects.create(
            when=date(2026, 7, 5), status=GameStatus.PLANNED, number_of_players=1
        )
        # user_1 cancelled, user_2 confirmed as their substitute
        # (capacity matches the single cancelled slot so the confirmed
        # player pairs with the cancellation instead of filling spare capacity)
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_1_per.player,
            status=StatusChoices.CANCELLED,
        )
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_2_per.player,
            status=StatusChoices.CONFIRMED,
        )
        self.status_update_url = reverse("game_status_update_url", args=[self.game.id])

    def test_substitute_gets_email_when_game_marked_played(self):
        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.PLAYED})

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, [self.user_2_per.email])
        self.assertIn("bolek", sent.body)
        self.assertIn("20.00", sent.body)

    def test_cancelled_player_without_substitute_gets_no_email(self):
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_3_per.player,
            status=StatusChoices.CANCELLED,
        )
        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.PLAYED})

        recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(recipients, {self.user_2_per.email})

    def test_no_email_sent_when_price_is_missing(self):
        GamePrice.objects.all().delete()
        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.PLAYED})

        self.assertEqual(len(mail.outbox), 0)

    def test_resaving_played_status_does_not_resend_email(self):
        self.client.force_login(self.superuser)
        self.client.post(self.status_update_url, {"status": GameStatus.PLAYED})
        self.client.post(
            self.status_update_url,
            {"status": GameStatus.PLAYED, "description": "updated"},
        )

        self.assertEqual(len(mail.outbox), 1)


class SubstitutePaymentTogglingTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # capacity matches the single cancelled slot so the confirmed
        # player pairs with the cancellation instead of filling spare capacity
        self.game = Game.objects.create(
            when=date(2026, 7, 5), status=GameStatus.PLAYED, number_of_players=1
        )
        self.cancelled_player = self.user_1_per.player
        self.substitute_player = self.user_2_per.player
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.cancelled_player,
            status=StatusChoices.CANCELLED,
        )
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.substitute_player,
            status=StatusChoices.CONFIRMED,
        )
        self.sent_url = reverse(
            "toggle_substitute_payment_sent_url", args=[self.game.id]
        )
        self.confirmed_url = reverse(
            "toggle_substitute_payment_confirmed_url", args=[self.game.id]
        )
        self.post_data = {
            "substitute_id": self.substitute_player.id,
            "cancelled_id": self.cancelled_player.id,
        }

    def test_substitute_can_mark_payment_as_sent(self):
        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)

        payment = SubstitutePayment.objects.get(
            game=self.game,
            cancelled_player=self.cancelled_player,
            substitute_player=self.substitute_player,
        )
        self.assertIsNotNone(payment.sent_at)
        self.assertIsNone(payment.confirmed_at)

    def test_toggling_sent_again_clears_it(self):
        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)
        self.client.post(self.sent_url, self.post_data)

        payment = SubstitutePayment.objects.get(
            game=self.game,
            cancelled_player=self.cancelled_player,
            substitute_player=self.substitute_player,
        )
        self.assertIsNone(payment.sent_at)

    def test_cancelled_player_can_confirm_payment(self):
        self.client.force_login(self.user_1_per)
        self.client.post(self.confirmed_url, self.post_data)

        payment = SubstitutePayment.objects.get(
            game=self.game,
            cancelled_player=self.cancelled_player,
            substitute_player=self.substitute_player,
        )
        self.assertIsNotNone(payment.confirmed_at)

    def test_other_player_cannot_mark_sent_on_someones_behalf(self):
        self.client.force_login(self.user_3_per)
        self.client.post(self.sent_url, self.post_data)

        self.assertFalse(SubstitutePayment.objects.exists())

    def test_other_player_cannot_confirm_on_someones_behalf(self):
        self.client.force_login(self.user_3_per)
        self.client.post(self.confirmed_url, self.post_data)

        self.assertFalse(SubstitutePayment.objects.exists())

    def test_superuser_can_toggle_both_sides(self):
        self.client.force_login(self.superuser)
        self.client.post(self.sent_url, self.post_data)
        self.client.post(self.confirmed_url, self.post_data)

        payment = SubstitutePayment.objects.get(
            game=self.game,
            cancelled_player=self.cancelled_player,
            substitute_player=self.substitute_player,
        )
        self.assertIsNotNone(payment.sent_at)
        self.assertIsNotNone(payment.confirmed_at)

    def test_game_details_shows_status_column_for_played_game(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("game_details_url", args=[self.game.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Awaiting")

        self.client.post(self.sent_url, self.post_data)
        response = self.client.get(reverse("game_details_url", args=[self.game.id]))
        self.assertContains(response, "Sent")

        self.client.post(self.confirmed_url, self.post_data)
        response = self.client.get(reverse("game_details_url", args=[self.game.id]))
        self.assertContains(response, "Confirmed")

    def test_game_details_hides_player_count_circle_for_played_game(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("game_details_url", args=[self.game.id]))

        self.assertNotContains(response, "radial-progress")

    def test_marking_sent_emails_cancelled_player_to_confirm(self):
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_1_per.email])
        self.assertIn("confirm", mail.outbox[0].body.lower())

    def test_toggling_sent_off_does_not_email(self):
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)
        self.client.post(self.sent_url, self.post_data)

        self.assertEqual(len(mail.outbox), 1)

    def test_marking_sent_without_cancelled_player_email_sends_no_email(self):
        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)

        self.assertEqual(len(mail.outbox), 0)

    def test_resending_after_already_confirmed_does_not_email(self):
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)

        self.client.force_login(self.user_1_per)
        self.client.post(self.confirmed_url, self.post_data)

        mail.outbox.clear()

        self.client.force_login(self.user_2_per)
        self.client.post(self.sent_url, self.post_data)
        self.client.post(self.sent_url, self.post_data)

        self.assertEqual(len(mail.outbox), 0)
