from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from games.helpers import settlement_helper
from games.models import (
    BookingHistoryForGame,
    Game,
    GamePrice,
    GameStatus,
    Player,
    PlayerRole,
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

    def test_permanent_player_can_view_who_paid(self):
        self.client.force_login(self.user_2_per)
        response = self.client.get(self.who_paid_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.who_paid_url)

    def test_reserve_player_cannot_view_who_paid(self):
        for role in (PlayerRole.ACTIVE, PlayerRole.INACTIVE):
            player = self.user_4_act.player
            player.role = role
            player.save()
            self.client.force_login(self.user_4_act)

            response = self.client.get(self.who_paid_url)
            self.assertEqual(response.status_code, 302, role)

            response = self.client.get(reverse("next_games_url"))
            self.assertNotContains(response, self.who_paid_url)

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

    def test_marking_unpaid_brings_back_the_payment_reminder(self):
        self.charge.sent_at = timezone.now()
        self.charge.save()
        self.client.force_login(self.user_1_per)
        toggle_url = reverse("toggle_paid_url", args=[self.charge.id])
        self.client.post(toggle_url, {"year": 2026, "month": 5})
        self.client.post(toggle_url, {"year": 2026, "month": 5})

        self.charge.refresh_from_db()
        self.assertIsNone(self.charge.sent_at)
        self.client.force_login(self.user_2_per)
        self.assertContains(self.client.get(reverse("next_games_url")), "Please pay")

    def test_who_paid_reflects_db_state(self):
        self.charge.is_paid = True
        self.charge.save()

        self.client.force_login(self.user_3_per)
        response = self.client.get(reverse("who_paid_url"), {"year": 2026, "month": 5})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paid")

    def test_who_paid_empty_state_does_not_error(self):
        self.client.force_login(self.user_3_per)
        response = self.client.get(reverse("who_paid_url"), {"year": 2099, "month": 1})
        self.assertEqual(response.status_code, 200)

    def test_toggle_marks_charge_paid_emails_the_player(self):
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

        self.client.force_login(self.user_1_per)
        self.client.post(
            reverse("toggle_paid_url", args=[self.charge.id]),
            {"year": 2026, "month": 5},
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_2_per.email])
        self.assertIn("payment received", mail.outbox[0].subject.lower())

    def test_toggling_unpaid_does_not_email(self):
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

        self.client.force_login(self.user_1_per)
        toggle_url = reverse("toggle_paid_url", args=[self.charge.id])
        self.client.post(toggle_url, {"year": 2026, "month": 5})
        self.client.post(toggle_url, {"year": 2026, "month": 5})

        self.assertEqual(len(mail.outbox), 1)

    def test_toggle_marks_charge_paid_without_player_email_sends_no_email(self):
        self.client.force_login(self.user_1_per)
        self.client.post(
            reverse("toggle_paid_url", args=[self.charge.id]),
            {"year": 2026, "month": 5},
        )

        self.assertEqual(len(mail.outbox), 0)


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

    def test_game_details_hides_reserve_list_for_played_game(self):
        for user in (self.user_2_per, self.superuser):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    reverse("game_details_url", args=[self.game.id])
                )

                self.assertNotContains(response, "Reserve List")

    def test_payment_status_is_visible_to_the_pair_and_admin(self):
        for user in (self.user_1_per, self.user_2_per, self.superuser):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    reverse("game_details_url", args=[self.game.id])
                )

                self.assertContains(response, self.confirmed_url)
                self.assertContains(response, self.sent_url)

    def test_payment_status_is_hidden_from_other_players(self):
        self.client.force_login(self.user_3_per)
        response = self.client.get(reverse("game_details_url", args=[self.game.id]))

        self.assertNotContains(response, self.confirmed_url)
        self.assertNotContains(response, self.sent_url)
        self.assertNotContains(response, "Awaiting")

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

    def test_confirming_payment_emails_the_substitute(self):
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

        self.client.force_login(self.user_1_per)
        self.client.post(self.confirmed_url, self.post_data)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_2_per.email])
        self.assertIn("confirmed", mail.outbox[0].subject.lower())

    def test_unconfirming_payment_does_not_email(self):
        self.user_2_per.email = "lolek@example.com"
        self.user_2_per.save()

        self.client.force_login(self.user_1_per)
        self.client.post(self.confirmed_url, self.post_data)
        self.client.post(self.confirmed_url, self.post_data)

        self.assertEqual(len(mail.outbox), 1)

    def test_confirming_payment_without_substitute_email_sends_no_email(self):
        self.client.force_login(self.user_1_per)
        self.client.post(self.confirmed_url, self.post_data)

        self.assertEqual(len(mail.outbox), 0)


class GameCostTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.accountant = self.user_1_per.player
        self.accountant.is_accountant = True
        self.accountant.save()

        self.game = Game.objects.create(
            when=date(2026, 3, 5), status=GameStatus.PLAYED, number_of_players=10
        )
        # a full roster: lolek plus nine more planned players
        self.roster = [self.user_2_per.player] + [
            self._create_player(f"roster_{idx}") for idx in range(9)
        ]
        for player in self.roster:
            self._book(player, StatusChoices.PLANNED)
        self.overview_url = reverse("settlement_overview_url")
        self.save_url = reverse("save_game_cost_url")
        self.send_url = reverse("send_settlement_url")
        self.client.force_login(self.user_1_per)

    @staticmethod
    def _create_player(username):
        user = get_user_model().objects.create_user(username=username)
        return Player.objects.create(user=user, mobile_number="123456789")

    def _book(self, player, status):
        BookingHistoryForGame.objects.create(
            game=self.game, player=player, status=status
        )

    def _charges(self, year=2026, month=3):
        return {
            settlement.player.user.username: settlement.total
            for settlement in settlement_helper.calculate_settlement(year, month)
        }

    def _charged(self, year=2026, month=3):
        return self._charges(year, month)["lolek"]

    def test_player_pays_game_cost_split_across_slots(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("275.00"))

        self.assertEqual(self._charged(), Decimal("27.50"))

    def test_cost_is_split_across_fewer_players_when_slots_stay_free(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("240.00"))
        self._book(self.roster[-1], StatusChoices.RESTING)
        self._book(self.roster[-2], StatusChoices.RESTING)

        charges = self._charges()

        self.assertEqual(len(charges), 8)
        self.assertEqual(set(charges.values()), {Decimal("30.00")})

    def test_cancelled_players_still_share_the_cost(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("240.00"))
        self._book(self.roster[-1], StatusChoices.RESTING)
        self._book(self.roster[-2], StatusChoices.CANCELLED)

        charges = self._charges()

        self.assertEqual(len(charges), 9)
        self.assertEqual(charges["roster_7"], Decimal("26.67"))

    def test_reserve_on_extra_slot_is_charged_and_shares_the_cost(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("240.00"))
        self._book(self.roster[-1], StatusChoices.RESTING)
        self._book(self.roster[-2], StatusChoices.RESTING)
        self._book(self.user_4_act.player, StatusChoices.CONFIRMED)

        charges = self._charges()

        self.assertEqual(len(charges), 9)
        self.assertEqual(charges["reksio"], Decimal("26.67"))
        self.assertEqual(charges["lolek"], Decimal("26.67"))

    def test_substitute_for_cancelled_player_is_not_charged(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("250.00"))
        self._book(self.roster[-1], StatusChoices.CANCELLED)
        self._book(self.user_4_act.player, StatusChoices.CONFIRMED)

        charges = self._charges()

        self.assertNotIn("reksio", charges)
        self.assertEqual(charges["roster_8"], Decimal("25.00"))

    def test_cost_is_not_split_across_more_players_than_slots(self):
        SettlementRun.objects.create(year=2026, month=3, game_cost=Decimal("250.00"))
        self._book(self._create_player("roster_extra"), StatusChoices.PLANNED)

        self.assertEqual(self._charged(), Decimal("25.00"))

    def test_legacy_price_is_not_split_across_fewer_players(self):
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))
        self._book(self.roster[-1], StatusChoices.RESTING)
        self._book(self.user_4_act.player, StatusChoices.CONFIRMED)

        charges = self._charges()

        self.assertEqual(charges["lolek"], Decimal("20.00"))
        self.assertNotIn("reksio", charges)

    def test_game_cost_defaults_to_previous_month(self):
        SettlementRun.objects.create(year=2026, month=1, game_cost=Decimal("250.00"))
        SettlementRun.objects.create(year=2026, month=2, game_cost=Decimal("300.00"))

        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})

        self.assertEqual(response.context["game_cost"], Decimal("300.00"))
        self.assertEqual(self._charged(), Decimal("30.00"))

    def test_later_month_cost_does_not_affect_earlier_month(self):
        SettlementRun.objects.create(year=2026, month=4, game_cost=Decimal("300.00"))
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))

        self.assertEqual(self._charged(), Decimal("20.00"))

    def test_accountant_can_save_game_cost(self):
        self.client.post(self.save_url, {"year": 2026, "month": 3, "game_cost": "280"})

        run = SettlementRun.objects.get(year=2026, month=3)
        self.assertEqual(run.game_cost, Decimal("280.00"))
        self.assertEqual(run.send_count, 0)

    def test_invalid_game_cost_is_rejected(self):
        for value in ["", "abc", "0", "-5", "NaN"]:
            with self.subTest(value=value):
                self.client.post(
                    self.save_url, {"year": 2026, "month": 3, "game_cost": value}
                )
                self.assertFalse(SettlementRun.objects.exists())

    def test_sending_stores_posted_game_cost(self):
        self.client.post(self.send_url, {"year": 2026, "month": 3, "game_cost": "260"})

        run = SettlementRun.objects.get(year=2026, month=3)
        self.assertEqual(run.game_cost, Decimal("260.00"))
        self.assertEqual(
            run.charges.get(player__user__username="lolek").amount, Decimal("26.00")
        )

    def test_sending_freezes_defaulted_game_cost(self):
        SettlementRun.objects.create(year=2026, month=2, game_cost=Decimal("300.00"))
        self.client.post(self.send_url, {"year": 2026, "month": 3})

        SettlementRun.objects.filter(year=2026, month=2).update(
            game_cost=Decimal("500.00")
        )

        self.assertEqual(
            SettlementRun.objects.get(year=2026, month=3).game_cost, Decimal("300.00")
        )
        self.assertEqual(self._charged(), Decimal("30.00"))

    def test_game_cost_is_locked_after_sending(self):
        self.client.post(self.send_url, {"year": 2026, "month": 3, "game_cost": "260"})

        self.client.post(self.save_url, {"year": 2026, "month": 3, "game_cost": "400"})
        self.client.post(self.send_url, {"year": 2026, "month": 3, "game_cost": "400"})

        run = SettlementRun.objects.get(year=2026, month=3)
        self.assertEqual(run.game_cost, Decimal("260.00"))
        self.assertEqual(run.send_count, 2)
        self.assertEqual(
            run.charges.get(player__user__username="lolek").amount, Decimal("26.00")
        )

    def test_game_cost_input_is_disabled_after_sending(self):
        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})
        self.assertNotContains(response, "Locked after the settlement was sent")

        self.client.post(self.send_url, {"year": 2026, "month": 3, "game_cost": "260"})

        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})
        self.assertContains(response, "Locked after the settlement was sent")

    def test_month_sent_with_per_player_price_shows_implied_game_cost(self):
        GamePrice.objects.create(amount=Decimal("27.00"), valid_from=date(2026, 1, 1))
        SettlementRun.objects.create(year=2026, month=3, send_count=1)

        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})

        self.assertEqual(response.context["game_cost"], Decimal("270.00"))
        self.assertContains(response, 'value="270.00"')

    def test_unsent_month_without_game_cost_stays_empty(self):
        GamePrice.objects.create(amount=Decimal("27.00"), valid_from=date(2026, 1, 1))

        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})

        self.assertIsNone(response.context["game_cost"])

    def test_saved_but_unsent_run_is_not_shown_as_sent(self):
        self.client.post(self.save_url, {"year": 2026, "month": 3, "game_cost": "280"})

        response = self.client.get(self.overview_url, {"year": 2026, "month": 3})

        self.assertFalse(response.context["is_sent"])
        self.assertNotContains(response, "already sent")


class MarkChargeSentTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        GamePrice.objects.create(amount=Decimal("20.00"), valid_from=date(2026, 1, 1))
        self.accountant = self.user_1_per
        self.accountant.email = "accountant@example.com"
        self.accountant.save()
        self.accountant.player.is_accountant = True
        self.accountant.player.save()

        game = Game.objects.create(when=date(2026, 5, 5), status=GameStatus.PLAYED)
        BookingHistoryForGame.objects.create(
            game=game, player=self.user_2_per.player, status=StatusChoices.PLANNED
        )
        self.run = settlement_helper.persist_settlement(2026, 5)
        self.charge = self.run.charges.get()
        self.mark_sent_url = reverse("mark_charge_sent_url", args=[self.charge.id])

    def test_player_marks_own_charge_sent_and_accountant_is_emailed(self):
        self.client.force_login(self.user_2_per)

        response = self.client.post(self.mark_sent_url)

        self.assertRedirects(response, f"{reverse('who_paid_url')}?year=2026&month=5")
        self.charge.refresh_from_db()
        self.assertIsNotNone(self.charge.sent_at)
        self.assertFalse(self.charge.is_paid)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["accountant@example.com"])
        self.assertIn("lolek", mail.outbox[0].subject)

    def test_marking_sent_twice_emails_once(self):
        self.client.force_login(self.user_2_per)
        self.client.post(self.mark_sent_url)
        self.client.post(self.mark_sent_url)

        self.assertEqual(len(mail.outbox), 1)

    def test_admins_are_emailed_when_no_accountant_has_email(self):
        self.accountant.email = ""
        self.accountant.save()
        self.client.force_login(self.user_2_per)

        self.client.post(self.mark_sent_url)

        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])

    def test_player_cannot_mark_someone_elses_charge_sent(self):
        self.client.force_login(self.user_3_per)

        self.client.post(self.mark_sent_url)

        self.charge.refresh_from_db()
        self.assertIsNone(self.charge.sent_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_who_paid_shows_button_only_on_own_unsent_charge(self):
        who_paid_url = reverse("who_paid_url")
        params = {"year": 2026, "month": 5}

        self.client.force_login(self.user_3_per)
        self.assertNotContains(
            self.client.get(who_paid_url, params), self.mark_sent_url
        )

        self.client.force_login(self.user_2_per)
        self.assertContains(self.client.get(who_paid_url, params), self.mark_sent_url)

        self.client.post(self.mark_sent_url)
        response = self.client.get(who_paid_url, params)
        self.assertNotContains(response, self.mark_sent_url)
        self.assertContains(response, "Sent, awaiting confirmation")

    def test_resending_settlement_keeps_sent_at(self):
        self.client.force_login(self.user_2_per)
        self.client.post(self.mark_sent_url)

        settlement_helper.persist_settlement(2026, 5)

        self.charge.refresh_from_db()
        self.assertIsNotNone(self.charge.sent_at)

    def test_permanent_player_sees_reminder_until_marked_sent(self):
        self.client.force_login(self.user_2_per)
        next_games_url = reverse("next_games_url")

        self.assertContains(self.client.get(next_games_url), "Please pay")

        self.client.post(self.mark_sent_url)
        self.assertNotContains(self.client.get(next_games_url), "Please pay")

    def test_reminder_disappears_once_paid(self):
        self.charge.is_paid = True
        self.charge.save()
        self.client.force_login(self.user_2_per)

        self.assertNotContains(self.client.get(reverse("next_games_url")), "Please pay")

    def test_non_permanent_player_gets_no_reminder(self):
        player = self.user_2_per.player
        player.role = PlayerRole.ACTIVE
        player.save()
        self.client.force_login(self.user_2_per)

        self.assertNotContains(self.client.get(reverse("next_games_url")), "Please pay")
