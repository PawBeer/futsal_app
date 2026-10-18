from futsal_app import settings
from games.models import BookingHistoryForGame, Game, Player, PlayerRole


def is_squad_member(user) -> bool:
    """Admins, accountants and permanent players. Only they may see the
    players list, profiles (with mobile numbers) and payments - reserves
    (active/inactive players) get what they need by email."""
    if user.is_superuser:
        return True
    player = getattr(user, "player", None)
    return bool(
        player and (player.role == PlayerRole.PERMANENT or player.is_accountant)
    )


def get_display_name(player: Player) -> str:
    display_mode = getattr(settings, "DISPLAY_NAME_MODE", "username")
    if display_mode == "username" and player.user:
        return player.user.username
    if display_mode == "full_name" and player.user:
        full_name = f"{player.user.first_name} {player.user.last_name}".strip()
        return full_name if full_name else player.user.username
    return "Unknown Player"


def get_display_name_for_user(user) -> str:
    player = getattr(user, "player", None)
    if player:
        return get_display_name(player)
    return user.get_username()


def get_latest_booking_for_game(
    player: Player, game: Game
) -> BookingHistoryForGame | None:
    return (
        BookingHistoryForGame.objects.filter(player=player, game=game)
        .order_by("-creation_date")
        .first()
    )
