from django.core import mail

from games.helpers import game_helper
from games.helpers.game_helper import get_total_players_for_game
from games.models import (
    BookingHistoryForGame,
    Game,
    Player,
    StatusChoices,
)

from .base import BaseTestCase


class AddGameViewTests(BaseTestCase):

    def test_post_with_set_players_creates_bookings_for_permanent_and_active(self):
        data = {
            "when": "2025-01-01",
            "status": "Planned",
            "description": "Test game with players",
            "set_players": "on",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        # view should redirect after successful POST
        self.assertEqual(response.status_code, 302)

        # the game should be created
        game = Game.objects.get(description="Test game with players")

        # bookings should be created for Permanent (planned) and Active (reserved) players
        bookings = BookingHistoryForGame.objects.filter(game=game)
        self.assertEqual(bookings.count(), 4)

        self.assertEqual(
            BookingHistoryForGame.objects.filter(
                game=game, status=StatusChoices.PLANNED
            ).count(),
            3,
        )
        self.assertEqual(
            BookingHistoryForGame.objects.filter(
                game=game, status=StatusChoices.STANDBY
            ).count(),
            1,
        )

    def test_post_without_set_players_creates_game_but_no_bookings(self):
        data = {
            "when": "2025-02-02",
            "status": "Planned",
            "description": "Test game without players",
            # no "set_players" key
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(description="Test game without players")
        bookings = BookingHistoryForGame.objects.filter(game=game)
        self.assertEqual(bookings.count(), 0)

    def test_transition_from_reserved_to_confirmed(self):
        data = {
            "when": "2025-03-03",
            "status": "Planned",
            "description": "Test game with reserved player",
            "set_players": "yes",
            # capacity matches the permanent roster so only a cancellation,
            # not spare capacity, opens up a confirm slot
            "number_of_players": "3",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(when="2025-03-03")

        # get a reserved player
        reserved_player = (
            BookingHistoryForGame.objects.filter(
                game=game, status=StatusChoices.STANDBY
            )
            .order_by("-creation_date")
            .first()
        ).player

        # now we have 3 players booked for the game (3 permanent /planned)
        self.assertEqual(get_total_players_for_game(game), 3)

        data = {
            "player_id": reserved_player.id,
            "checked": "on",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)

        # now the reserved player should be awaiting hence still 3 players booked
        self.assertEqual(get_total_players_for_game(game), 3)

    def test_transition_from_reserved_to_awaiting_to_confirmed(self):
        data = {
            "when": "2025-03-03",
            "status": "Planned",
            "description": "Test game with reserved player",
            "set_players": "yes",
            # capacity matches the permanent roster so only a cancellation,
            # not spare capacity, opens up a confirm slot
            "number_of_players": "3",
        }

        # Login as superuser and make POST using test client
        self.client.force_login(self.superuser)
        response = self.client.post("/games/add_game", data)

        self.assertEqual(response.status_code, 302)

        game = Game.objects.get(when="2025-03-03")

        # get a reserved player
        reserved_player = (
            BookingHistoryForGame.objects.filter(
                game=game, status=StatusChoices.STANDBY
            )
            .order_by("-creation_date")
            .first()
        ).player

        # now we have 3 players booked for the game (3 permanent /planned)
        self.assertEqual(get_total_players_for_game(game), 3)

        data = {
            "player_id": reserved_player.id,
            "checked": "on",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)

        # now the reserved player should be awaiting hence still 3 players booked
        self.assertEqual(get_total_players_for_game(game), 3)

        # lets cancel one planned player and that would move awaiting to confirmed
        bolek_player = Player.objects.get(user=self.user_1_per)
        data = {
            "player_id": bolek_player.id,
            "checked": "off",
        }
        response = self.client.post(
            f"/games/game/{game.id}/update-player-status/", data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            len(game_helper.get_players_by_status([StatusChoices.AWAITING], game)), 0
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([StatusChoices.PLANNED], game)), 2
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([StatusChoices.CONFIRMED], game)), 1
        )
        self.assertEqual(
            len(game_helper.get_players_by_status([StatusChoices.CANCELLED], game)), 1
        )
        self.assertEqual(get_total_players_for_game(game), 3)

    def test_promoting_awaiting_player_emails_both_players_and_one_admin_mail(self):
        # cancelling a permanent while a substitute is awaiting a slot
        # auto-promotes that substitute - both players should be emailed
        # about their own status change, and admins should get a single
        # combined email rather than one per change.
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()
        self.user_4_act.email = "reksio@example.com"
        self.user_4_act.save()

        data = {
            "when": "2025-03-03",
            "status": "Planned",
            "description": "Test game with reserved player",
            "set_players": "yes",
            "number_of_players": "3",
        }
        self.client.force_login(self.superuser)
        self.client.post("/games/add_game", data)

        game = Game.objects.get(when="2025-03-03")

        reserved_player = (
            BookingHistoryForGame.objects.filter(
                game=game, status=StatusChoices.STANDBY
            )
            .order_by("-creation_date")
            .first()
        ).player
        self.client.post(
            f"/games/game/{game.id}/update-player-status/",
            {"player_id": reserved_player.id, "checked": "on"},
        )

        mail.outbox.clear()

        bolek_player = Player.objects.get(user=self.user_1_per)
        self.client.post(
            f"/games/game/{game.id}/update-player-status/",
            {"player_id": bolek_player.id, "checked": "off"},
        )

        player_emails = [m for m in mail.outbox if m.to == ["bolek@example.com"]]
        player_emails += [m for m in mail.outbox if m.to == ["reksio@example.com"]]
        admin_emails = [m for m in mail.outbox if m.to == ["admin@example.com"]]

        self.assertEqual(len(player_emails), 2)
        self.assertEqual(len(admin_emails), 1)
        self.assertEqual(len(mail.outbox), 3)

    def test_notifications_enabled_toggle_is_saved_by_superuser(self):
        data = {
            "when": "2025-04-04",
            "status": "Planned",
            "description": "Test game",
        }
        self.client.force_login(self.superuser)
        self.client.post("/games/add_game", data)
        game = Game.objects.get(when="2025-04-04")
        self.assertTrue(game.notifications_enabled)

        # the "Update Game Details" form always submits this hidden marker
        # alongside the checkbox, so a POST missing it (e.g. from another
        # caller) leaves notifications_enabled untouched
        self.client.post(
            f"/games/game/{game.id}/update-status/",
            {"status": "Planned", "description": "Test game"},
        )
        game.refresh_from_db()
        self.assertTrue(game.notifications_enabled)

        self.client.post(
            f"/games/game/{game.id}/update-status/",
            {
                "status": "Planned",
                "description": "Test game",
                "notifications_enabled_submitted": "1",
            },
        )
        game.refresh_from_db()
        self.assertFalse(game.notifications_enabled)

        self.client.post(
            f"/games/game/{game.id}/update-status/",
            {
                "status": "Planned",
                "description": "Test game",
                "notifications_enabled_submitted": "1",
                "notifications_enabled": "on",
            },
        )
        game.refresh_from_db()
        self.assertTrue(game.notifications_enabled)

    def test_no_emails_sent_when_notifications_disabled_for_game(self):
        self.user_1_per.email = "bolek@example.com"
        self.user_1_per.save()

        data = {
            "when": "2025-05-05",
            "status": "Planned",
            "description": "Test game",
            "set_players": "yes",
            "number_of_players": "3",
        }
        self.client.force_login(self.superuser)
        self.client.post("/games/add_game", data)
        game = Game.objects.get(when="2025-05-05")
        game.notifications_enabled = False
        game.save()

        mail.outbox.clear()

        bolek_player = Player.objects.get(user=self.user_1_per)
        self.client.post(
            f"/games/game/{game.id}/update-player-status/",
            {"player_id": bolek_player.id, "checked": "off"},
        )

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            len(game_helper.get_players_by_status([StatusChoices.CANCELLED], game)), 1
        )
