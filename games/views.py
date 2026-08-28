import calendar
from datetime import datetime, time, timedelta
from typing import Iterable

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.core.paginator import Paginator
from django.core.signing import BadSignature
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from games.forms import PlayerProfileForm
from games.helpers import game_helper, player_helper, settlement_helper, token_helper
from games.mailer import (
    send_player_status_update_email,
    send_player_status_updates_email_to_admins,
    send_settlement_email,
    send_substitute_payment_confirmation_request_email,
    send_substitute_payment_email,
    send_welcome_email,
)

from .models import (
    BookingHistoryForGame,
    ChatMessage,
    Game,
    GameStatus,
    Player,
    PlayerCharge,
    PlayerRole,
    PlayerStatus,
    SettlementRun,
    StatusChoices,
    SubstitutePayment,
    User,
)

User = get_user_model()


class Breadcrumb:
    def __init__(self, path, label):
        self.path = path
        self.label = label


def method_not_allowed(request, exception=None):
    """Handles requests using a disallowed HTTP method (e.g. a bookmarked
    or shared GET link to a POST-only view such as logout) instead of
    letting the user land on a blank 405 response."""
    messages.info(request, "Ta strona nie obsługuje takiego żądania.")
    redirect_url = "next_games_url" if request.user.is_authenticated else "login_url"
    return redirect(redirect_url)


class LogoutView(DjangoLogoutView):
    """Logout is only allowed via POST (see DjangoLogoutView). Visiting the
    logout URL directly, e.g. via a bookmarked or shared link, previously
    resulted in a blank 405 response; redirect the user instead."""

    def http_method_not_allowed(self, request, *args, **kwargs):
        return method_not_allowed(request)


@login_required
def next_games(request):
    found_games = (
        Game.objects.filter(when__gte=datetime.today())
        .exclude(status="Played")
        .select_related()
        .order_by("when")
        .prefetch_related("bookinghistoryforgame_set")
    )

    for game in found_games:
        game.number_of_booked_players = game_helper.get_number_of_booked_players(game)

    return render(request, "games/next_games.html", {"games": found_games})


@login_required
def past_games(request):
    found_games = (
        Game.objects.filter(Q(when__lt=datetime.today()) | Q(status=GameStatus.PLAYED))
        .order_by("-when")
        .all()
    )
    games_paginator = Paginator(found_games, 20)
    games_page_number = request.GET.get("games_page")
    games_page_obj = games_paginator.get_page(games_page_number)
    return render(request, "games/past_games.html", {"games": games_page_obj})


def _player_should_see_reserved_table(
    user: AbstractBaseUser, players: Iterable[Player]
) -> bool:
    player = getattr(user, "player", None)
    if player is None:
        return True  # admins may not have a player
    return player in players


def _pair_cancelled_with_substitutes_and_payment(game: Game):
    pairs = game_helper.pair_cancelled_with_substitutes(game)
    payments = {
        (payment.cancelled_player_id, payment.substitute_player_id): payment
        for payment in SubstitutePayment.objects.filter(game=game)
    }
    return [
        (
            cancelled_player,
            substitute,
            payments.get((cancelled_player.id, substitute.id)) if substitute else None,
        )
        for cancelled_player, substitute in pairs
    ]


@login_required
def game_details(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    planned_players = game_helper.get_players_by_status([StatusChoices.PLANNED], game)
    cancelled_players = game_helper.get_players_by_status(
        [StatusChoices.CANCELLED], game
    )
    standby_players = game_helper.get_players_by_status([StatusChoices.STANDBY], game)
    confirmed_players = game_helper.get_players_by_status(
        [StatusChoices.CONFIRMED], game
    )
    awaiting_players = game_helper.get_players_by_status(
        [StatusChoices.AWAITING], game, order_by="latest_creation_date"
    )

    is_past_game = game.when < timezone.now().date()
    if is_past_game:
        active_link = "Past games"
        active_url = reverse("past_games_url")
    else:
        active_link = "Next games"
        active_url = reverse("next_games_url")

    breadcrumbs = [
        Breadcrumb(active_url, active_link),
        Breadcrumb(reverse("game_details_url", args=[game.id]), game.when),
    ]

    return render(
        request,
        "games/game_details.html",
        {
            "game": game,
            "planned_players_for_game": planned_players,
            "standby_players_for_game": standby_players,
            "confirmed_players_for_game": confirmed_players,
            "awaiting_players_for_game": awaiting_players,
            "number_of_booked_players": len(planned_players)
            + len(confirmed_players)
            + len(awaiting_players),
            "warning_threshold": max(1, round(game.number_of_players * 0.8)),
            "number_of_confirmed_players": len(confirmed_players),
            "cancelled_with_substitutes": _pair_cancelled_with_substitutes_and_payment(
                game
            ),
            "extra_capacity_slots": game_helper.get_extra_capacity_slots(game),
            "has_open_slot": game_helper.has_open_slot(game),
            "number_of_cancelled_players": len(cancelled_players),
            "booking_history": BookingHistoryForGame.objects.filter(game=game).order_by(
                "-creation_date"
            ),
            "status_options": GameStatus.labels,
            "is_past_game": is_past_game,
            "breadcrumbs": breadcrumbs,
            "player_should_see_reserved_table": _player_should_see_reserved_table(
                request.user,
                standby_players + confirmed_players + awaiting_players,
            ),
        },
    )


@login_required
def game_remove(request, game_id):
    found_game = get_object_or_404(Game, id=game_id)

    if request.method == "POST":
        found_game.delete()
        messages.success(request, "Game was successfully removed.")
        return redirect("next_games_url")

    return render(request, "games/game_confirm_remove.html", {"game": found_game})


def _notify_substitutes_of_payment(game: Game) -> None:
    """
    For a game that just became Played, email every confirmed player who
    took over a cancelled player's slot, telling them how much to send
    that player (the price valid on the game's date).
    """
    amount = settlement_helper.get_price_for_game(game.when)
    if amount is None:
        return

    for cancelled_player, substitute in game_helper.pair_cancelled_with_substitutes(
        game
    ):
        if substitute is None or not substitute.user or not substitute.user.email:
            continue
        send_substitute_payment_email(substitute, cancelled_player, game, amount)


def _date_has_game(when_date, exclude_game_id=None) -> bool:
    """Whether a game (regardless of status) already exists on `when_date`."""
    conflicting = Game.objects.filter(when=when_date)
    if exclude_game_id is not None:
        conflicting = conflicting.exclude(id=exclude_game_id)
    return conflicting.exists()


def _default_reminder_send_at(when_date):
    """Default weekly-reminder send time: 2 days before the game, in the
    morning. Editable afterwards via 'Update Game Details'."""
    when_only = when_date.date() if hasattr(when_date, "date") else when_date
    return timezone.make_aware(
        datetime.combine(when_only - timedelta(days=2), time(8, 0))
    )


@login_required
@require_POST
def game_status_update(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    status_value = request.POST.get("status")
    description = request.POST.get("description")
    when_value = request.POST.get("when")
    previous_status = game.status

    if status_value:
        game.status = status_value
    if description is not None:
        game.description = description
    if when_value and request.user.is_superuser:
        try:
            when_date = datetime.strptime(when_value, "%Y-%m-%d")
        except ValueError:
            messages.error(request, "Invalid date.")
            return redirect("game_details_url", game_id=game_id)

        if _date_has_game(when_date, exclude_game_id=game.id):
            messages.error(
                request,
                f"A game is already scheduled on {when_date:%d %b %Y}.",
            )
            return redirect("game_details_url", game_id=game_id)

        if when_date.date() != game.when:
            game.reminder_sent_at = None
        game.when = when_date

    if request.user.is_superuser and request.POST.get(
        "notifications_enabled_submitted"
    ):
        game.notifications_enabled = "on" == request.POST.get("notifications_enabled")

    if request.user.is_superuser and request.POST.get("reminder_enabled_submitted"):
        game.reminder_enabled = "on" == request.POST.get("reminder_enabled")

        reminder_send_at = request.POST.get("reminder_send_at")
        if reminder_send_at:
            try:
                game.reminder_send_at = timezone.make_aware(
                    datetime.strptime(reminder_send_at, "%Y-%m-%dT%H:%M")
                )
            except ValueError:
                messages.error(request, "Invalid reminder send date/time.")

    game.save()

    if (
        previous_status != GameStatus.PLAYED
        and game.status == GameStatus.PLAYED
        and game.notifications_enabled
    ):
        _notify_substitutes_of_payment(game)

    return redirect("game_details_url", game_id=game_id)


def _check_if_empty_slots(game):
    if game_helper.has_open_slot(game):
        return StatusChoices.CONFIRMED

    return StatusChoices.AWAITING


def _uncancel_if_slot_available(game):
    # a permanent who cancelled can only switch back to Planned if a slot
    # is still open - if substitutes already confirmed into every open
    # slot, they stay Cancelled
    if game_helper.has_open_slot(game):
        return StatusChoices.PLANNED

    return StatusChoices.CANCELLED


def _apply_status_change_logic(current_status, checked, game):
    status_handler = {
        (StatusChoices.PLANNED, False): lambda game: StatusChoices.CANCELLED,
        (StatusChoices.CANCELLED, True): _uncancel_if_slot_available,
        (StatusChoices.STANDBY, True): _check_if_empty_slots,
        (StatusChoices.AWAITING, True): _check_if_empty_slots,
        (StatusChoices.AWAITING, False): lambda game: StatusChoices.STANDBY,
        (StatusChoices.CONFIRMED, False): lambda game: StatusChoices.STANDBY,
        (StatusChoices.PLANNED, True): lambda game: StatusChoices.PLANNED,
    }
    try:
        return status_handler[(current_status, checked)](game)
    except KeyError:
        raise ValueError(f"No handler for status={current_status}, checked={checked}")


def _apply_transition_from_awaiting_to_confirmed(game):
    """If cancelling/unchecking a player freed up a slot, promote the
    longest-waiting awaiting player to confirmed. Returns the (player,
    status) change so the caller can include it in a single admin email
    instead of sending a separate one here."""
    awaiting_players = game_helper.get_players_by_status(
        [StatusChoices.AWAITING], game, order_by="latest_creation_date"
    )
    if len(awaiting_players) > 0:

        if StatusChoices.CONFIRMED == _check_if_empty_slots(game):
            player_to_confirm = awaiting_players[0]
            BookingHistoryForGame.objects.create(
                player=player_to_confirm,
                game=game,
                status=StatusChoices.CONFIRMED,
                creation_date=timezone.now(),
            )
            if game.notifications_enabled:
                send_player_status_update_email(
                    player_to_confirm, game, StatusChoices.CONFIRMED
                )
            return player_to_confirm, StatusChoices.CONFIRMED

    return None


def _apply_player_status_change(game: Game, player: Player, current_status, checked):
    """
    Shared core of a player status change: computes the new status, records
    it, promotes an awaiting player into any freed slot, and sends the
    relevant notification emails. Returns (new_status, changes) so callers
    with different failure/redirect handling (an authenticated form post vs.
    an anonymous one-click cancel link) can each report the outcome their
    own way.
    """
    new_status = _apply_status_change_logic(current_status, checked, game)

    changes = []

    if current_status != new_status:
        BookingHistoryForGame.objects.create(
            player=player,
            game=game,
            status=new_status,
            creation_date=timezone.now(),
        )
        if game.notifications_enabled:
            send_player_status_update_email(player, game, new_status)
        changes.append((player, new_status))

    promoted_change = _apply_transition_from_awaiting_to_confirmed(game)
    if promoted_change:
        changes.append(promoted_change)

    if changes and game.notifications_enabled:
        send_player_status_updates_email_to_admins(changes, game)

    return new_status, changes


@login_required
@require_POST
def game_player_status_update(request, game_id):
    found_game = get_object_or_404(Game, id=game_id)

    if found_game.status != "Planned" and not request.user.is_superuser:
        messages.error(request, "Can only change status for Planned games.")
        return redirect("game_details_url", game_id=game_id)

    player_pk = request.POST.get("player_id")
    checked = "on" == request.POST.get("checked")

    player = get_object_or_404(Player, pk=player_pk)

    if not (request.user.is_superuser or player.user == request.user):
        messages.error(request, "You can only change your own status.")
        return redirect("game_details_url", game_id=game_id)

    if not BookingHistoryForGame.objects.filter(
        player=player, game=found_game
    ).exists():
        messages.error(request, "Player not found in this game.")
        return redirect("game_details_url", game_id=game_id)

    current_booking = player_helper.get_latest_booking_for_game(player, found_game)
    current_status = current_booking.status if current_booking else None

    new_status, _changes = _apply_player_status_change(
        found_game, player, current_status, checked
    )

    if current_status == new_status == StatusChoices.CANCELLED and checked:
        messages.error(
            request,
            "No free slot available - a substitute has already taken this spot.",
        )

    return redirect("game_details_url", game_id=game_id)


def cancel_participation_via_link(request, token):
    """
    One-click, no-login cancel link sent in the weekly availability reminder
    email. The token is scoped to a specific game+player (see
    games.helpers.token_helper) and stops working once the game date passes.
    """
    try:
        payload = token_helper.read_cancel_token(token)
        game = get_object_or_404(Game, id=payload["game_id"])
        player = get_object_or_404(Player, id=payload["player_id"])
    except (BadSignature, KeyError):
        return render(
            request, "games/cancel_participation_result.html", {"invalid": True}
        )

    if game.when < timezone.now().date():
        return render(
            request,
            "games/cancel_participation_result.html",
            {"expired": True, "game": game},
        )

    current_booking = player_helper.get_latest_booking_for_game(player, game)
    current_status = current_booking.status if current_booking else None

    if current_status == StatusChoices.CANCELLED:
        return render(
            request,
            "games/cancel_participation_result.html",
            {"already_cancelled": True, "game": game, "player": player},
        )

    _apply_player_status_change(game, player, current_status, checked=False)

    return render(
        request,
        "games/cancel_participation_result.html",
        {"game": game, "player": player},
    )


def _get_substitute_payment_pair(request):
    substitute = get_object_or_404(Player, pk=request.POST.get("substitute_id"))
    cancelled_player = get_object_or_404(Player, pk=request.POST.get("cancelled_id"))
    return substitute, cancelled_player


@login_required
@require_POST
def toggle_substitute_payment_sent(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    substitute, cancelled_player = _get_substitute_payment_pair(request)

    if not (request.user.is_superuser or substitute.user == request.user):
        messages.error(request, "You can only mark your own payment as sent.")
        return redirect("game_details_url", game_id=game_id)

    payment, _created = SubstitutePayment.objects.get_or_create(
        game=game, cancelled_player=cancelled_player, substitute_player=substitute
    )
    marking_as_sent = payment.sent_at is None
    payment.sent_at = timezone.now() if marking_as_sent else None
    payment.save(update_fields=["sent_at"])

    if (
        marking_as_sent
        and not payment.confirmed_at
        and cancelled_player.user
        and cancelled_player.user.email
    ):
        send_substitute_payment_confirmation_request_email(payment)

    return redirect("game_details_url", game_id=game_id)


@login_required
@require_POST
def toggle_substitute_payment_confirmed(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    substitute, cancelled_player = _get_substitute_payment_pair(request)

    if not (request.user.is_superuser or cancelled_player.user == request.user):
        messages.error(request, "You can only confirm payments sent to you.")
        return redirect("game_details_url", game_id=game_id)

    payment, _created = SubstitutePayment.objects.get_or_create(
        game=game, cancelled_player=cancelled_player, substitute_player=substitute
    )
    payment.confirmed_at = None if payment.confirmed_at else timezone.now()
    payment.save(update_fields=["confirmed_at"])

    return redirect("game_details_url", game_id=game_id)


@login_required
def all_players(request):
    filter_name = request.GET.get("name", "").strip()
    status = request.GET.get("status")

    stat_counts = Player.objects.aggregate(
        total_players=Count("id"),
        permanent_players=Count("id", filter=Q(role=PlayerRole.PERMANENT)),
        active_players=Count("id", filter=Q(role=PlayerRole.ACTIVE)),
        inactive_players=Count("id", filter=Q(role=PlayerRole.INACTIVE)),
    )

    players = Player.objects.all()
    if filter_name and len(filter_name) > 1:
        players = players.filter(
            Q(user__first_name__icontains=filter_name)
            | Q(user__last_name__icontains=filter_name)
            | Q(user__username__icontains=filter_name)
        )

    if status and status in ["permanent", "active", "inactive"]:
        players = players.filter(role=status.capitalize())

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "games/_players_table.html", {"players": players})

    return render(
        request,
        "games/all_players.html",
        {
            "filter": filter_name,
            "players": players,
            "details": stat_counts,
            "status": status,
        },
    )


@login_required
def player_details(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    # bind the profile form (template uses plain input names that match the form fields)
    profile_form = PlayerProfileForm(request.POST or None, instance=player)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if not request.user.is_superuser:
            messages.error(request, "You don't have permission to edit this profile.")
            return redirect("player_details_url", player_id=player.id)
        if form_type == "profile":
            if profile_form.is_valid():
                new_username = profile_form.cleaned_data.get("username")
                if (
                    User.objects.filter(username=new_username)
                    .exclude(id=player.user.id)
                    .exists()
                ):
                    messages.error(request, "This username already exists.")
                else:
                    try:
                        profile_form.save()
                        messages.success(request, "Profile updated successfully.")
                        return redirect("player_details_url", player_id=player.id)
                    except IntegrityError:
                        messages.error(
                            request, "An error occurred while saving the profile."
                        )
            else:
                # collect form errors and show them as a message so template (which uses raw inputs) can display
                errors = []
                for field, field_errors in profile_form.errors.items():
                    errors.extend([f"{field}: {e}" for e in field_errors])
                messages.error(request, "Invalid data: " + "; ".join(errors))

        elif form_type == "welcome_email":
            # build a sensible activation link (fallback to next_games)
            activation_link = request.build_absolute_uri(reverse("password_reset"))
            send_welcome_email(player.user, activation_link)
            messages.success(request, "Welcome email has been sent.")
            return redirect("player_details_url", player_id=player.id)
    return render(
        request,
        "games/player_details.html",
        {
            "player": player,
            "player_role_choices": PlayerRole.choices,
            "breadcrumbs": [
                Breadcrumb(reverse("all_players_url"), "All Players"),
                Breadcrumb(
                    reverse("player_details_url", args=[player.id]),
                    player_helper.get_display_name(player),
                ),
            ],
        },
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_player(request):
    if request.method == "POST":
        profile_form = PlayerProfileForm(request.POST)
        if profile_form.is_valid():
            new_username = profile_form.cleaned_data.get("username")
            if User.objects.filter(username=new_username).exists():
                messages.error(request, "This username already exists.")
            else:
                try:
                    profile_form.save()
                    messages.success(request, "Player added successfully.")
                    return redirect("all_players_url")
                except IntegrityError:
                    messages.error(
                        request, "An error occurred while saving the player."
                    )
        else:
            # collect form errors and show them as a message so template (which uses raw inputs) can display
            errors = []
            for field, field_errors in profile_form.errors.items():
                errors.extend([f"{field}: {e}" for e in field_errors])
            messages.error(request, "Invalid data: " + "; ".join(errors))

    context = {
        "role_choices": PlayerRole.choices,
    }
    return render(request, "games/add_player.html", context)


@login_required
def check_username_and_email(request):
    username = request.GET.get("username")
    email = request.GET.get("email")

    username_exists = (
        User.objects.filter(username=username).exists() if username else False
    )
    email_exists = User.objects.filter(email=email).exists() if email else False

    return JsonResponse(
        {
            "username_exists": username_exists,
            "email_exists": email_exists,
        }
    )


@login_required()
def booking_history(request):
    page_size = request.GET.get("page_size", 25)
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 25
    page_size = max(5, min(page_size, 100))

    player_id = request.GET.get("player_id", "")
    status = request.GET.get("status", "")

    found_booking_history = BookingHistoryForGame.objects.all().order_by("-id")
    if player_id:
        found_booking_history = found_booking_history.filter(player_id=player_id)
    if status:
        found_booking_history = found_booking_history.filter(status=status)

    paginator = Paginator(found_booking_history, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "games/booking_history.html",
        {
            "booking_history": page_obj,
            "page_size": page_size,
            "page_sizes": [10, 25, 50, 100],
            "players": Player.objects.all().order_by(
                "user__first_name", "user__last_name"
            ),
            "status_choices": StatusChoices.choices,
            "selected_player_id": player_id,
            "selected_status": status,
        },
    )


def _create_booking_for_players(game: Game, players: Iterable[Player], status):
    for player in players:
        BookingHistoryForGame.objects.create(game=game, player=player, status=status)


def _parse_number_of_players(raw_value):
    try:
        number_of_players = int(raw_value)
    except (TypeError, ValueError):
        return 10
    return max(1, number_of_players)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_game(request):
    if request.method == "POST":
        when_date = datetime.strptime(request.POST.get("when", ""), "%Y-%m-%d")

        if _date_has_game(when_date):
            messages.error(
                request,
                f"A game is already scheduled on {when_date:%d %b %Y}.",
            )
            return render(
                request,
                "games/add_game.html",
                {"role_choices": GameStatus.choices},
            )

        number_of_players = _parse_number_of_players(
            request.POST.get("number_of_players", 10)
        )

        game = Game.objects.create(
            when=when_date,
            status=request.POST.get("status", GameStatus.PLANNED),
            description=request.POST.get("description", ""),
            number_of_players=number_of_players,
            reminder_send_at=_default_reminder_send_at(when_date),
        )
        if request.POST.get("set_players"):

            _create_booking_for_players(
                game,
                Player.objects.filter(role=PlayerRole.PERMANENT),
                StatusChoices.PLANNED,
            )
            _create_booking_for_players(
                game,
                Player.objects.filter(role=PlayerRole.ACTIVE),
                StatusChoices.STANDBY,
            )

            psm_list = PlayerStatus.objects.all().order_by("date_start")
            game_date = game.when.date() if hasattr(game.when, "date") else game.when

            for psm in psm_list:
                if psm.date_start <= game_date <= psm.date_end:
                    if psm.status == StatusChoices.RESTING:
                        games_in_range = Game.objects.filter(
                            when__gte=psm.date_start, when__lte=psm.date_end
                        )
                        game_helper.apply_status_to_games_in_range(
                            psm.player, games_in_range, psm.status
                        )
                    else:
                        BookingHistoryForGame.objects.create(
                            game=game, player=psm.player, status=psm.status
                        )

        return redirect("next_games_url")

    return render(
        request,
        "games/add_game.html",
        {
            "role_choices": GameStatus.choices,
        },
    )


@login_required
def add_absence(request):
    players = Player.objects.all()
    if request.user.is_superuser:
        status = PlayerStatus.objects.all().order_by("-id")
    else:
        status = PlayerStatus.objects.filter(player__user=request.user).order_by("-id")
    status_paginator = Paginator(status, 15)
    status_page_number = request.GET.get("status_page")
    status_page_obj = status_paginator.get_page(status_page_number)

    if request.method == "POST":
        player_id = request.POST.get("player")
        date_start_str = request.POST.get("date_start")
        date_end_str = request.POST.get("date_end")
        status = request.POST.get("status")
        description = request.POST.get("description", "").strip()

        try:
            player = Player.objects.get(pk=player_id)
            date_start = datetime.strptime(date_start_str, "%Y-%m-%d")
            date_end = datetime.strptime(date_end_str, "%Y-%m-%d")

            PlayerStatus.objects.create(
                player=player,
                date_start=date_start,
                date_end=date_end,
                status=status,
                description=description,
            )

            games_in_range = Game.objects.filter(
                when__gte=date_start, when__lte=date_end
            )
            game_helper.apply_status_to_games_in_range(player, games_in_range, status)

            messages.success(
                request, f"Absence for {player.user.username} has been added."
            )
            return redirect("next_games_url")

        except Player.DoesNotExist:
            messages.error(request, "Selected player does not exist.")
        except Exception as e:
            messages.error(request, f"Error while adding absence: {e}")

    return render(
        request,
        "games/add_absence.html",
        {
            "players": players,
            "status_choices": StatusChoices.filtered_choices(
                exclude=[StatusChoices.AWAITING]
            ),
            "status": status_page_obj,
        },
    )


CHAT_HISTORY_LIMIT = 50
CHAT_MESSAGE_MAX_LENGTH = 1000


def _serialize_chat_message(chat_message, request_user):
    return {
        "id": chat_message.id,
        "author": player_helper.get_display_name_for_user(chat_message.user),
        "message": chat_message.message,
        "created_at": timezone.localtime(chat_message.created_at).strftime(
            "%d %b %Y, %H:%M"
        ),
        "is_own": chat_message.user_id == request_user.id,
    }


@login_required
def chat_messages(request):
    since_id = request.GET.get("since_id")

    if since_id is None:
        found_messages = list(
            ChatMessage.objects.select_related("user", "user__player").order_by("-id")[
                :CHAT_HISTORY_LIMIT
            ]
        )
        found_messages.reverse()
    else:
        try:
            since_id = int(since_id)
        except ValueError:
            since_id = 0
        found_messages = ChatMessage.objects.select_related(
            "user", "user__player"
        ).filter(id__gt=since_id)

    return JsonResponse(
        {"messages": [_serialize_chat_message(m, request.user) for m in found_messages]}
    )


def _is_accountant_or_superuser(user):
    if user.is_superuser:
        return True
    player = getattr(user, "player", None)
    return bool(player and player.is_accountant)


accountant_required = user_passes_test(_is_accountant_or_superuser)


def _default_period():
    """Last calendar month, since settlements are typically run in arrears."""
    today = timezone.now().date()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _resolve_period(request, source=None):
    source = source if source is not None else request.GET
    default_year, default_month = _default_period()
    try:
        year = int(source.get("year", default_year))
        month = int(source.get("month", default_month))
    except (TypeError, ValueError):
        year, month = default_year, default_month
    if not 1 <= month <= 12:
        month = default_month
    return year, month


def _period_choices():
    """Year and (number, name) month choices for the period-picker dropdowns."""
    today = timezone.now().date()
    earliest_game = Game.objects.order_by("when").first()
    start_year = (
        min(earliest_game.when.year, today.year) if earliest_game else today.year
    )
    year_choices = list(range(start_year, today.year + 2))
    month_choices = list(enumerate(calendar.month_name))[1:]
    return year_choices, month_choices


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
    year_choices, month_choices = _period_choices()

    return render(
        request,
        "games/settlement_overview.html",
        {
            "year": year,
            "month": month,
            "year_choices": year_choices,
            "month_choices": month_choices,
            "settlements": settlements,
            "missing_price_games": missing_price_games,
            "run": run,
            "charges": charges,
        },
    )


@login_required
@require_POST
def chat_send(request):
    text = request.POST.get("message", "").strip()
    if not text:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    chat_message = ChatMessage.objects.create(
        user=request.user, message=text[:CHAT_MESSAGE_MAX_LENGTH]
    )
    return JsonResponse(_serialize_chat_message(chat_message, request.user))


@login_required
@accountant_required
@require_POST
def send_settlement(request):
    year, month = _resolve_period(request, source=request.POST)
    run = settlement_helper.persist_settlement(year, month)

    sent = 0
    for charge in run.charges.select_related("player__user"):
        if charge.is_paid:
            continue
        if not charge.player.user or not charge.player.user.email:
            continue
        send_settlement_email(charge)
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
    year_choices, month_choices = _period_choices()

    return render(
        request,
        "games/who_paid.html",
        {
            "year": year,
            "month": month,
            "year_choices": year_choices,
            "month_choices": month_choices,
            "run": run,
            "charges": charges,
        },
    )
