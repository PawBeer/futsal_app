from django.db.models import Max, OuterRef, Subquery

from games.models import (
    BookingHistoryForGame,
    Game,
    Player,
    StatusChoices,
)


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
        .filter(latest_status__in=[StatusChoices.CONFIRMED, StatusChoices.PLANNED])
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
        status__in=[StatusChoices.PLANNED, StatusChoices.CONFIRMED],
        creation_date__in=latest_bookings,
    ).count()
    return booked_count


def has_open_slot(game: Game) -> bool:
    """
    A slot is open whenever fewer players are currently committed (planned
    permanents + already-confirmed reserves) than the game's configured
    capacity - this covers both cancellation replacements and extra
    capacity beyond the permanent roster.
    """
    planned_count = len(get_players_by_status([StatusChoices.PLANNED], game))
    confirmed_count = len(get_players_by_status([StatusChoices.CONFIRMED], game))
    return planned_count + confirmed_count < game.number_of_players


def _get_extra_slot_count(game: Game, cancelled_count: int) -> int:
    planned_count = len(get_players_by_status([StatusChoices.PLANNED], game))
    permanent_roster_size = planned_count + cancelled_count
    return max(0, game.number_of_players - permanent_roster_size)


def get_extra_capacity_slots(game: Game) -> list[Player | None]:
    """
    Returns one entry per capacity slot beyond the game's original permanent
    roster (planned + cancelled players). Confirmed reserves fill these
    slots first, in confirmation order - only confirmations beyond that are
    used to replace a cancelled permanent (see pair_cancelled_with_substitutes).
    """
    cancelled_players = get_players_by_status([StatusChoices.CANCELLED], game)
    extra_slot_count = _get_extra_slot_count(game, len(cancelled_players))
    if extra_slot_count == 0:
        return []

    confirmed_players = get_players_by_status([StatusChoices.CONFIRMED], game)

    return [
        confirmed_players[idx] if idx < len(confirmed_players) else None
        for idx in range(extra_slot_count)
    ]


def pair_cancelled_with_substitutes(game: Game) -> list[tuple[Player, Player | None]]:
    """
    Pairs each cancelled player for the game with the confirmed player who
    took their slot (matched by order), or None if the slot is still free.
    Confirmed reserves are assigned to extra-capacity slots first (see
    get_extra_capacity_slots), so only the confirmations beyond that are
    available here to replace a cancellation.
    """
    cancelled_players = get_players_by_status([StatusChoices.CANCELLED], game)
    extra_slot_count = _get_extra_slot_count(game, len(cancelled_players))
    confirmed_players = get_players_by_status([StatusChoices.CONFIRMED], game)
    remaining_confirmed_players = confirmed_players[extra_slot_count:]

    pairs = []
    for idx, cancelled_player in enumerate(cancelled_players):
        substitute = (
            remaining_confirmed_players[idx]
            if idx < len(remaining_confirmed_players)
            else None
        )
        pairs.append((cancelled_player, substitute))
    return pairs


def apply_status_to_games_in_range(player: Player, games_in_range, status: str) -> None:
    """
    Records `status` as the player's booking for each game in
    `games_in_range`. When `status` is Resting and the player already has a
    booking for a game, they're downgraded to Cancelled (if they were
    Planned/Cancelled) or Standby (if they were Confirmed/Standby) instead
    of being force-marked Resting, so existing slot/substitute bookkeeping
    for that game isn't clobbered.
    """
    for game in games_in_range:
        latest_booking = (
            BookingHistoryForGame.objects.filter(player=player, game=game)
            .order_by("-creation_date")
            .first()
        )

        if status == StatusChoices.RESTING and latest_booking:
            current_status = latest_booking.status
            if current_status in [StatusChoices.PLANNED, StatusChoices.CANCELLED]:
                new_status = StatusChoices.CANCELLED
            elif current_status in [StatusChoices.CONFIRMED, StatusChoices.STANDBY]:
                new_status = StatusChoices.STANDBY
            else:
                new_status = status
        else:
            new_status = status

        BookingHistoryForGame.objects.create(
            game=game, player=player, status=new_status
        )
