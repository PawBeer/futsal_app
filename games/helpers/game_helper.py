from django.db.models import OuterRef, Subquery

from games.models import BookingHistoryForGame, Game, Player
from games.models import PlayerStatus


def get_players_by_status(statuses: list[str], game: Game) -> list[Player]:
    """
    Returns a list of players for a given game filtered by their booking status.
    """
    latest_status_sq = (
        BookingHistoryForGame.objects.filter(player=OuterRef("pk"), game=game)
        .order_by("-creation_date")
        .values("status")[:1]
    )

    players = (
        Player.objects.filter(status_history__game=game)
        .annotate(latest_status=Subquery(latest_status_sq))
        .filter(latest_status__in=statuses)
        .distinct()
    )

    return list(players)


# @todo refactor status strings into constants somewhere central
# #todo try to simplify the queries below
def get_total_players_for_game(game: Game) -> int:
    """
    Returns the total number of players booked for a given game.
    """
    latest_status_sq = (
        BookingHistoryForGame.objects.filter(player=OuterRef("pk"), game=game)
        .order_by("-creation_date")
        .values("status")[:1]
    )

    return (
        Player.objects.filter(status_history__game=game)
        .annotate(latest_status=Subquery(latest_status_sq))
        .filter(latest_status__in=[PlayerStatus.CONFIRMED, PlayerStatus.PLANNED])
        .distinct()
        .count()
    )
