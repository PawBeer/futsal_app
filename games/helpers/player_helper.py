from futsal_app import settings
from games.models import BookingHistoryForGame, Game, Player


def get_display_name(player: Player) -> str:
    display_mode = getattr(settings, "DISPLAY_NAME_MODE", "username")
    if display_mode == "username" and player.user:
        return player.user.username
    if display_mode == "full_name" and player.user:
        full_name = f"{player.user.first_name} {player.user.last_name}".strip()
        return full_name if full_name else player.user.username
    return "Unknown Player"


def get_latest_booking_for_game(
    player: Player, game: Game
) -> BookingHistoryForGame | None:
    return (
        BookingHistoryForGame.objects.filter(player=player, game=game)
        .order_by("-creation_date")
        .first()
    )
