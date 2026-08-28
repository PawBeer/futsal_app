from django.core import signing

from games.models import Game, Player

CANCEL_PARTICIPATION_SALT = "games.cancel-participation"
CONFIRM_PARTICIPATION_SALT = "games.confirm-participation"
CANCEL_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days: signature staleness guard


def make_cancel_token(game: Game, player: Player) -> str:
    return signing.dumps(
        {"game_id": game.id, "player_id": player.id}, salt=CANCEL_PARTICIPATION_SALT
    )


def read_cancel_token(token: str) -> dict:
    """
    Decodes a cancel-participation token, raising BadSignature/SignatureExpired
    on a tampered or stale token. This only guards against garbage tokens - real
    expiry is tied to the game date and must be checked separately by the caller.
    """
    return signing.loads(
        token,
        salt=CANCEL_PARTICIPATION_SALT,
        max_age=CANCEL_TOKEN_MAX_AGE_SECONDS,
    )


def make_confirm_token(game: Game, player: Player) -> str:
    return signing.dumps(
        {"game_id": game.id, "player_id": player.id}, salt=CONFIRM_PARTICIPATION_SALT
    )


def read_confirm_token(token: str) -> dict:
    """
    Decodes a confirm-participation token (sent to standby players), raising
    BadSignature/SignatureExpired on a tampered or stale token. This only
    guards against garbage tokens - real expiry is tied to the game date and
    must be checked separately by the caller.
    """
    return signing.loads(
        token,
        salt=CONFIRM_PARTICIPATION_SALT,
        max_age=CANCEL_TOKEN_MAX_AGE_SECONDS,
    )
