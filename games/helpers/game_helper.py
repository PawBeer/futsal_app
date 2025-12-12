from django.db.models import OuterRef, Subquery
from django.db.models import Max

from games.models import BookingHistoryForGame, Game, Player, PlayerStatus


def get_players_by_status(
    statuses: list[str], game: Game, order_by="latest_creation_date"
) -> list[Player]:
    """
    Returns players filtered by their latest booking status,
    ordered by the creation date of their latest booking history entry.
    """

    latest_history_sq = BookingHistoryForGame.objects.filter(
        player=OuterRef("pk"), game=game
    ).order_by(
        "-creation_date"
    )  # always choose latest by creation_date

    players = (
        Player.objects.filter(status_history__game=game)
        .annotate(
            latest_status=Subquery(latest_history_sq.values("status")[:1]),
            latest_creation_date=Subquery(
                latest_history_sq.values("creation_date")[:1]
            ),
        )
        .filter(latest_status__in=statuses)
        .distinct()
        .order_by(order_by)  # e.g. "-latest_creation_date"
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


def get_number_of_booked_players(game):
    """Number of players with resent status PLANNED/CONFIRMED"""
    latest_bookings = (
        BookingHistoryForGame.objects.filter(game=game)
        .values("player")
        .annotate(latest_date=Max("creation_date"))
        .values_list("latest_date", flat=True)
    )

    booked_count = BookingHistoryForGame.objects.filter(
        game=game,
        status__in=[PlayerStatus.PLANNED, PlayerStatus.CONFIRMED],
        creation_date__in=latest_bookings,
    ).count()
    return booked_count
