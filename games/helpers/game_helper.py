from django.db.models import OuterRef, Subquery

from games.models import Game
from games.models import BookingHistoryForGame, Player


def get_total_players_for_game(game: Game) -> int:
    """
    Returns the total number of players booked for a given game.
    """
    # We need to consider only the newest BookingHistoryForGame entry per
    # player for the given game. Use a Subquery to fetch the latest
    # player_status.player_status (string) for each Player and then count
    # Players whose latest status is in the allowed list.
    latest_status_sq = (
        BookingHistoryForGame.objects.filter(player=OuterRef("pk"), game=game)
        .order_by("-creation_date")
        .values("player_status__player_status")[:1]
    )

    return (
        Player.objects.filter(status_history__game=game)
        .annotate(latest_status=Subquery(latest_status_sq))
        .filter(latest_status__in=["confirmed", "planned"])
        .distinct()
        .count()
    )
