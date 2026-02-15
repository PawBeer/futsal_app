import json
from django.urls import reverse
from django.utils import timezone
from games.models import (
    Game,
    GameStatus,
    StatusChoices,
    BookingHistoryForGame,
    GoalEvent,
    Player,
)
from .base import BaseTestCase


class ApiIntegrationTests(BaseTestCase):
    """
    Test suite for the Watch API endpoints: Roster and Match Synchronization.
    """

    def setUp(self):
        super().setUp()
        # Create a test game instance
        self.game = Game.objects.create(
            when=timezone.now().date(),
            description="API Test Game",
            status=GameStatus.PLANNED,
        )

        # Set up booking history for players from BaseTestCase
        # User 1 (Bolek) - Confirmed
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_1_per.player,
            status=StatusChoices.CONFIRMED,
        )
        # User 2 (Lolek) - Planned
        BookingHistoryForGame.objects.create(
            game=self.game, player=self.user_2_per.player, status=StatusChoices.PLANNED
        )
        # User 3 (Tola) - Cancelled (Should not appear in the roster)
        BookingHistoryForGame.objects.create(
            game=self.game,
            player=self.user_3_per.player,
            status=StatusChoices.CANCELLED,
        )

    def test_game_roster_endpoint_filtering(self):
        """
        Verify that the roster endpoint returns only active players
        (Confirmed or Planned) and excludes Cancelled ones.
        """
        url = reverse("game-roster", kwargs={"game_id": self.game.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # We expect 2 players: bolek and lolek. tola is cancelled, reksio has no booking.
        self.assertEqual(len(data), 2)

        player_names = [p["name"] for p in data]
        self.assertIn("bolek", player_names)
        self.assertIn("lolek", player_names)
        self.assertNotIn("tola", player_names)

    def test_match_sync_successful_upload(self):
        """
        Test the bulk synchronization of goal events from the watch to the server.
        Ensures goals are created and the game status is updated to 'Played'.
        """
        url = reverse("match-sync")

        bolek_player = self.user_1_per.player
        goal_time = timezone.now().isoformat()

        # Simulated JSON payload from the watch
        payload = {
            "game_id": self.game.id,
            "status": GameStatus.PLAYED,
            "goals": [
                {
                    "team": "black",
                    "scorer": bolek_player.id,
                    "own_goal": False,
                    "created_at": goal_time,
                },
                {
                    "team": "white",
                    "scorer": None,
                    "own_goal": True,
                    "created_at": goal_time,
                },
            ],
        }

        # Send POST request as application/json
        response = self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(GoalEvent.objects.filter(game=self.game).count(), 2)

        # Verify that the game status has transitioned to Played
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, GameStatus.PLAYED)

    def test_match_sync_idempotency(self):
        """
        Verify that re-syncing the same match overwrites previous goal data
        instead of duplicating it. Important for unreliable Bluetooth connections.
        """
        # Create a "stale" goal event manually
        GoalEvent.objects.create(
            game=self.game, team="black", created_at=timezone.now()
        )

        url = reverse("match-sync")
        payload = {
            "game_id": self.game.id,
            "status": GameStatus.PLAYED,
            "goals": [
                {
                    "team": "white",
                    "scorer": self.user_2_per.player.id,
                    "own_goal": False,
                    "created_at": timezone.now().isoformat(),
                }
            ],
        }

        self.client.post(url, data=json.dumps(payload), content_type="application/json")

        # Previous goal should be deleted, only the new one should exist
        self.assertEqual(GoalEvent.objects.filter(game=self.game).count(), 1)
        latest_goal = GoalEvent.objects.first()
        self.assertEqual(latest_goal.team, "white")

    def test_match_sync_non_existent_game(self):
        """
        Verify that the API returns a 404 error if an invalid game_id is provided.
        """
        url = reverse("match-sync")
        payload = {"game_id": 9999, "goals": []}

        response = self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_match_sync_malformed_data(self):
        """
        Verify that the API returns a 400 error if the payload is missing required fields.
        """
        url = reverse("match-sync")
        # Missing "game_id"
        payload = {"goals": []}

        response = self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
