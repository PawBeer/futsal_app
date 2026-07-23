import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

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


def _price_lookup():
    """Returns a function mapping a game date to the price valid on that date."""
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
    cancelled, charged at the price valid on that game's date.
    """
    start_date, end_date = get_period_bounds(year, month)
    price_for = _price_lookup()

    settlements = {}
    for game in get_qualifying_games(start_date, end_date):
        amount = price_for(game.when) or Decimal("0.00")
        for player in game_helper.get_players_by_status(CHARGEABLE_STATUSES, game):
            settlement = settlements.setdefault(
                player.id, PlayerSettlement(player=player)
            )
            settlement.lines.append(ChargeLine(game=game, amount=amount))

    return sorted(
        settlements.values(), key=lambda s: player_helper.get_display_name(s.player)
    )


def get_price_for_game(when: date) -> Decimal | None:
    """Returns the price valid on the given game date, or None if not set."""
    return _price_lookup()(when)


def games_missing_price(year: int, month: int) -> list:
    """Qualifying games with no GamePrice valid on or before their date."""
    start_date, end_date = get_period_bounds(year, month)
    price_for = _price_lookup()
    return [
        game
        for game in get_qualifying_games(start_date, end_date)
        if price_for(game.when) is None
    ]


def persist_settlement(year: int, month: int) -> SettlementRun:
    """
    Creates (or reuses) the SettlementRun for the period and upserts each
    player's PlayerCharge with the freshly calculated amount/game_count,
    without touching is_paid/paid_at/marked_by on existing charges.
    """
    run, _ = SettlementRun.objects.get_or_create(year=year, month=month)

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
