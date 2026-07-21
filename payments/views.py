from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import mailer
from .helpers import settlement_helper
from .models import PlayerCharge, SettlementRun


def _is_accountant_or_superuser(user):
    if user.is_superuser:
        return True
    player = getattr(user, "player", None)
    return bool(player and player.is_accountant)


accountant_required = user_passes_test(_is_accountant_or_superuser)


def _resolve_period(request, source=None):
    source = source if source is not None else request.GET
    today = timezone.now().date()
    try:
        year = int(source.get("year", today.year))
        month = int(source.get("month", today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month
    if not 1 <= month <= 12:
        month = today.month
    return year, month


@login_required
@accountant_required
def settlement_overview(request):
    year, month = _resolve_period(request)
    settlements = settlement_helper.calculate_settlement(year, month)
    missing_price_games = settlement_helper.games_missing_price(year, month)
    run = SettlementRun.objects.filter(year=year, month=month).first()
    charges = (
        run.charges.select_related("player__user").order_by("player__user__username")
        if run
        else []
    )

    return render(
        request,
        "payments/settlement_overview.html",
        {
            "year": year,
            "month": month,
            "settlements": settlements,
            "missing_price_games": missing_price_games,
            "run": run,
            "charges": charges,
        },
    )


@login_required
@accountant_required
@require_POST
def send_settlement(request):
    year, month = _resolve_period(request, source=request.POST)
    run = settlement_helper.persist_settlement(year, month)

    sent = 0
    for charge in run.charges.select_related("player__user"):
        if not charge.player.user or not charge.player.user.email:
            continue
        mailer.send_settlement_email(charge)
        sent += 1

    run.send_count += 1
    run.last_sent_at = timezone.now()
    run.save(update_fields=["send_count", "last_sent_at"])

    messages.success(request, f"Settlement sent to {sent} player(s).")
    return redirect(f"{reverse('settlement_overview_url')}?year={year}&month={month}")


@login_required
@accountant_required
@require_POST
def toggle_paid(request, charge_id):
    charge = get_object_or_404(PlayerCharge, id=charge_id)
    charge.is_paid = not charge.is_paid
    charge.paid_at = timezone.now() if charge.is_paid else None
    charge.marked_by = request.user
    charge.save()

    year, month = _resolve_period(request, source=request.POST)
    return redirect(f"{reverse('settlement_overview_url')}?year={year}&month={month}")


@login_required
def who_paid(request):
    year, month = _resolve_period(request)
    run = SettlementRun.objects.filter(year=year, month=month).first()
    charges = (
        run.charges.select_related("player__user", "marked_by").order_by(
            "player__user__username"
        )
        if run
        else []
    )

    return render(
        request,
        "payments/who_paid.html",
        {"year": year, "month": month, "run": run, "charges": charges},
    )
