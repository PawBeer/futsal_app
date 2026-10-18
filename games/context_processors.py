from games.helpers import player_helper
from games.models import PlayerCharge, PlayerRole


def player_access(request):
    return {"is_squad_member": player_helper.is_squad_member(request.user)}


def pending_payments(request):
    """Settlement charges a logged-in permanent player still has to pay and
    hasn't yet marked as sent, shown as a reminder on top of every page."""
    if not request.user.is_authenticated:
        return {}
    charges = (
        PlayerCharge.objects.filter(
            player__user=request.user,
            player__role=PlayerRole.PERMANENT,
            is_paid=False,
            sent_at__isnull=True,
        )
        .select_related("settlement_run")
        .order_by("settlement_run__year", "settlement_run__month")
    )
    return {"pending_payment_charges": charges}
