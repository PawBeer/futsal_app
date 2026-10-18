import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

from games.helpers import game_helper, player_helper
from games.models import (
    Game,
    GamePrice,
    GameStatus,
    Player,
    PlayerCharge,
    SettlementRun,
    StatusChoices,
)

CHARGEABLE_STATUSES = [StatusChoices.PLANNED, StatusChoices.CANCELLED]
SETTLEMENT_GAME_STATUSES = [GameStatus.PLAYED, GameStatus.CANCELLED]


def get_period_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) inclusive for the given calendar month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def get_qualifying_games(start_date: date, end_date: date):
    """Games that actually took place or were cancelled within the period."""
    return Game.objects.filter(
        when__gte=start_date, when__lte=end_date, status__in=SETTLEMENT_GAME_STATUSES
    ).order_by("when")


def get_game_cost(year: int, month: int) -> Decimal | None:
    """
    Whole-game cost for the period: the one set for it, otherwise the one
    from the most recent earlier period that has it.
    """
    run = (
        SettlementRun.objects.filter(game_cost__isnull=False)
        .filter(Q(year__lt=year) | Q(year=year, month__lte=month))
        .order_by("-year", "-month")
        .first()
    )
    return run.game_cost if run else None


def get_legacy_game_cost(year: int, month: int) -> Decimal | None:
    """
    Whole-game cost implied by a period billed with the per-player GamePrice
    (before game costs were set): the latest game's price times its slots.
    """
    start_date, end_date = get_period_bounds(year, month)
    price_for = _legacy_price_lookup()
    for game in get_qualifying_games(start_date, end_date).reverse():
        price = price_for(game.when)
        if price is not None:
            return price * game.number_of_players
    return None


def _legacy_price_lookup():
    """Returns a function mapping a game date to the per-player GamePrice valid then."""
    prices = list(GamePrice.objects.order_by("valid_from"))

    def price_for(when: date):
        applicable = None
        for price in prices:
            if price.valid_from <= when:
                applicable = price
            else:
                break
        return applicable.amount if applicable else None

    return price_for


class _Pricing:
    """
    Prices games for a settlement. With a game cost set for the period, the
    cost is split across the players charged for the game - planned and
    cancelled players plus confirmed reserves on extra slots - so slots
    nobody filled are covered by those who played (never dividing by more
    than the game's number of players). Periods from before game costs were
    set fall back to the per-player GamePrice.
    """

    def __init__(self):
        self._legacy_price_for = _legacy_price_lookup()
        self._game_costs = {}

    def _game_cost(self, game: Game) -> Decimal | None:
        period = (game.when.year, game.when.month)
        if period not in self._game_costs:
            self._game_costs[period] = get_game_cost(*period)
        return self._game_costs[period]

    def _uses_game_cost(self, game: Game) -> bool:
        return self._game_cost(game) is not None and bool(game.number_of_players)

    def charged_players(self, game: Game) -> list:
        players = game_helper.get_players_by_status(CHARGEABLE_STATUSES, game)
        if self._uses_game_cost(game):
            players += [
                player
                for player in game_helper.get_extra_capacity_slots(game)
                if player is not None
            ]
        return players

    def price_for(self, game: Game, charged_players=None) -> Decimal | None:
        if not self._uses_game_cost(game):
            return self._legacy_price_for(game.when)
        if charged_players is None:
            charged_players = self.charged_players(game)
        divisor = min(len(charged_players), game.number_of_players)
        return (self._game_cost(game) / (divisor or game.number_of_players)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass
class ChargeLine:
    game: Game
    amount: Decimal


@dataclass
class PlayerSettlement:
    player: Player
    lines: list = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0.00"))

    @property
    def game_count(self) -> int:
        return len(self.lines)


def calculate_settlement(year: int, month: int) -> list:
    """
    Read-only preview of who owes what for a period: every player whose latest
    booking status on a Played/Cancelled game within the period is planned or
    cancelled (plus, when the period has a game cost, confirmed reserves on
    extra slots), charged at that game's price (see _Pricing).
    """
    start_date, end_date = get_period_bounds(year, month)
    pricing = _Pricing()

    settlements = {}
    for game in get_qualifying_games(start_date, end_date):
        players = pricing.charged_players(game)
        amount = pricing.price_for(game, players) or Decimal("0.00")
        for player in players:
            settlement = settlements.setdefault(
                player.id, PlayerSettlement(player=player)
            )
            settlement.lines.append(ChargeLine(game=game, amount=amount))

    return sorted(
        settlements.values(), key=lambda s: player_helper.get_display_name(s.player)
    )


def get_price_for_game(game: Game) -> Decimal | None:
    """Returns the price each player pays for the game, or None if not set."""
    return _Pricing().price_for(game)


def games_missing_price(year: int, month: int) -> list:
    """Qualifying games with no price to charge for them."""
    start_date, end_date = get_period_bounds(year, month)
    pricing = _Pricing()
    return [
        game
        for game in get_qualifying_games(start_date, end_date)
        if pricing.price_for(game) is None
    ]


def persist_settlement(year: int, month: int) -> SettlementRun:
    """
    Creates (or reuses) the SettlementRun for the period and upserts each
    player's PlayerCharge with the freshly calculated amount/game_count,
    without touching is_paid/paid_at/marked_by on existing charges.
    """
    run, _ = SettlementRun.objects.get_or_create(year=year, month=month)
    if run.game_cost is None:
        # Freeze the defaulted cost so later changes to other periods
        # can't alter what was billed for this one.
        run.game_cost = get_game_cost(year, month)
        run.save(update_fields=["game_cost"])

    for settlement in calculate_settlement(year, month):
        PlayerCharge.objects.update_or_create(
            settlement_run=run,
            player=settlement.player,
            defaults={
                "amount": settlement.total,
                "game_count": settlement.game_count,
            },
        )

    return run
