from datetime import datetime
from typing import Iterable

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from games.forms import PlayerProfileForm
from games.helpers import game_helper, player_helper
from games.mailer import (
    send_player_status_update_email,
    send_player_status_update_email_to_admins,
    send_welcome_email,
)

from .models import (
    BookingHistoryForGame,
    Game,
    GameStatus,
    Player,
    PlayerRole,
    PlayerStatus,
    StatusChoices,
    User,
)

User = get_user_model()


class Breadcrumb:
    def __init__(self, path, label):
        self.path = path
        self.label = label


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


def _apply_substitute_to_cancelled_players(
    cancelled: list[Player], confirmed: list[Player]
) -> list[tuple[Player, Player]]:
    cancelled_with_substitutes = []
    for idx, cancelled_player in enumerate(cancelled):
        substitute = confirmed[idx] if idx < len(confirmed) else None
        cancelled_with_substitutes.append((cancelled_player, substitute))
    return cancelled_with_substitutes


@login_required
def game_details(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    planned_players = game_helper.get_players_by_status([StatusChoices.PLANNED], game)
    cancelled_players = game_helper.get_players_by_status(
        [StatusChoices.CANCELLED], game
    )
    reserved_players = game_helper.get_players_by_status([StatusChoices.RESERVED], game)
    confirmed_players = game_helper.get_players_by_status(
        [StatusChoices.CONFIRMED], game
    )
    awaiting_players = game_helper.get_players_by_status(
        [StatusChoices.AWAITING], game, order_by="latest_creation_date"
    )

    if game.when < timezone.now().date():
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
            "reserved_players_for_game": reserved_players,
            "confirmed_players_for_game": confirmed_players,
            "awaiting_players_for_game": awaiting_players,
            "number_of_booked_players": len(planned_players) + len(confirmed_players),
            "number_of_confirmed_players": len(confirmed_players),
            "cancelled_with_substitutes": _apply_substitute_to_cancelled_players(
                cancelled=cancelled_players, confirmed=confirmed_players
            ),
            "number_of_cancelled_players": len(cancelled_players),
            "booking_history": BookingHistoryForGame.objects.filter(game=game).order_by(
                "-creation_date"
            ),
            "status_options": GameStatus.labels,
            "breadcrumbs": breadcrumbs,
            "player_should_see_reserved_table": _player_should_see_reserved_table(
                request.user,
                reserved_players + confirmed_players + awaiting_players,
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


@login_required
@require_POST
def game_status_update(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    status_value = request.POST.get("status")
    description = request.POST.get("description")

    if status_value:
        game.status = status_value
    if description is not None:
        game.description = description
    game.save()
    return redirect("game_details_url", game_id=game_id)


def _check_if_empty_slots(game):
    # function to determine if there are empty slots
    cancelled_count = len(
        game_helper.get_players_by_status([StatusChoices.CANCELLED], game)
    )
    confirmed_count = len(
        game_helper.get_players_by_status([StatusChoices.CONFIRMED], game)
    )

    if cancelled_count > confirmed_count:
        return StatusChoices.CONFIRMED

    return StatusChoices.AWAITING


def _apply_status_change_logic(current_status, checked, game):
    status_handler = {
        (StatusChoices.PLANNED, False): lambda game: StatusChoices.CANCELLED,
        (StatusChoices.CANCELLED, True): lambda game: StatusChoices.PLANNED,
        (StatusChoices.RESERVED, True): lambda game: StatusChoices.AWAITING,
        (StatusChoices.AWAITING, True): _check_if_empty_slots,
        (StatusChoices.AWAITING, False): lambda game: StatusChoices.RESERVED,
        (StatusChoices.CONFIRMED, False): lambda game: StatusChoices.RESERVED,
        (StatusChoices.PLANNED, True): lambda game: StatusChoices.PLANNED,
    }
    try:
        return status_handler[(current_status, checked)](game)
    except KeyError:
        raise ValueError(f"No handler for status={current_status}, checked={checked}")


def _apply_transition_from_awaiting_to_confirmed(game):
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
            send_player_status_update_email(
                player_to_confirm, game, StatusChoices.CONFIRMED
            )
            send_player_status_update_email_to_admins(
                player_to_confirm, game, StatusChoices.CONFIRMED
            )


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

    new_status = _apply_status_change_logic(current_status, checked, found_game)

    if current_status != new_status:
        BookingHistoryForGame.objects.create(
            player=player,
            game=found_game,
            status=new_status,
            creation_date=timezone.now(),
        )
        send_player_status_update_email(player, found_game, new_status)
        send_player_status_update_email_to_admins(player, found_game, new_status)

    _apply_transition_from_awaiting_to_confirmed(found_game)

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

    found_booking_history = BookingHistoryForGame.objects.all().order_by("-id")
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
        },
    )


def _create_booking_for_players(game: Game, players: Iterable[Player], status):
    for player in players:
        BookingHistoryForGame.objects.create(game=game, player=player, status=status)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_game(request):
    if request.method == "POST":
        game = Game.objects.create(
            when=datetime.strptime(request.POST.get("when", ""), "%Y-%m-%d"),
            status=request.POST.get("status", GameStatus.PLANNED),
            description=request.POST.get("description", ""),
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
                StatusChoices.RESERVED,
            )

            psm_list = PlayerStatus.objects.all().order_by("date_start")
            game_date = game.when.date() if hasattr(game.when, "date") else game.when

            for psm in psm_list:
                if psm.date_start <= game_date <= psm.date_end:
                    if psm.status == StatusChoices.RESTING:
                        games_in_range = Game.objects.filter(
                            when__gte=psm.date_start, when__lte=psm.date_end
                        )
                        for game_in_range in games_in_range:
                            latest_booking = (
                                BookingHistoryForGame.objects.filter(
                                    player=psm.player, game=game_in_range
                                )
                                .order_by("-creation_date")
                                .first()
                            )

                            if latest_booking:
                                current_status_key = latest_booking.status
                                if current_status_key in [
                                    StatusChoices.PLANNED,
                                    StatusChoices.CANCELLED,
                                ]:
                                    new_status = StatusChoices.CANCELLED
                                elif current_status_key in [
                                    StatusChoices.CONFIRMED,
                                    StatusChoices.RESERVED,
                                ]:
                                    new_status = StatusChoices.RESERVED
                                else:
                                    new_status = psm.status
                            else:
                                new_status = psm.status

                            BookingHistoryForGame.objects.create(
                                game=game_in_range, player=psm.player, status=new_status
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

            resting_status_key = StatusChoices.RESTING

            for game in games_in_range:
                latest_booking = (
                    BookingHistoryForGame.objects.filter(player=player, game=game)
                    .order_by("-creation_date")
                    .first()
                )

                if status == resting_status_key and latest_booking:
                    current_status_key = latest_booking.status
                    if current_status_key in [
                        StatusChoices.PLANNED,
                        StatusChoices.CANCELLED,
                    ]:
                        new_status = StatusChoices.CANCELLED
                    elif current_status_key in [
                        StatusChoices.CONFIRMED,
                        StatusChoices.RESERVED,
                    ]:
                        new_status = StatusChoices.RESERVED
                    else:
                        new_status = status
                else:
                    new_status = status

                BookingHistoryForGame.objects.create(
                    player=player,
                    game=game,
                    status=new_status,
                    creation_date=timezone.now(),
                )
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
