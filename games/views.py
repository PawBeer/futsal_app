from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from games.helpers import game_helper, player_helper
from games.mailer import (
    send_player_status_update_email,
    send_player_status_update_email_to_admins,
)

from .models import BookingHistoryForGame, Game, Player, PlayerStatus, User

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
        .order_by("when")
        .all()
    )
    return render(request, "games/next_games.html", {"games": found_games})


@login_required
def past_games(request):
    found_games = (
        Game.objects.filter(Q(when__lt=datetime.today()) | Q(status="Played"))
        .order_by("-when")
        .all()
    )
    games_paginator = Paginator(found_games, 20)
    games_page_number = request.GET.get("games_page")
    games_page_obj = games_paginator.get_page(games_page_number)
    return render(request, "games/past_games.html", {"games": games_page_obj})


@login_required
def game_details(request, game_id):
    found_game = get_object_or_404(Game, id=game_id)

    planned_players_for_game = game_helper.get_players_by_status(
        [PlayerStatus.PLANNED], found_game
    )
    cancelled_players_for_game = game_helper.get_players_by_status(
        [PlayerStatus.CANCELLED], found_game
    )
    reserved_players_for_game = game_helper.get_players_by_status(
        [PlayerStatus.RESERVED], found_game
    )
    confirmed_players_for_game = game_helper.get_players_by_status(
        [PlayerStatus.CONFIRMED], found_game
    )
    number_of_confirmed_players = len(planned_players_for_game) + len(
        confirmed_players_for_game
    )
    found_booking_history = BookingHistoryForGame.objects.filter(
        game=found_game
    ).order_by("-creation_date")
    status_options = [choice[0] for choice in Game.STATUS_CHOICES]

    cancelled_with_substitutes = []
    for idx, cancelled_player in enumerate(cancelled_players_for_game):
        substitute = (
            confirmed_players_for_game[idx]
            if idx < len(confirmed_players_for_game)
            else None
        )
        cancelled_with_substitutes.append((cancelled_player, substitute))

    return render(
        request,
        "games/game_details.html",
        {
            "game": found_game,
            "planned_players_for_game": planned_players_for_game,
            "reserved_players_for_game": reserved_players_for_game,
            "confirmed_players_for_game": confirmed_players_for_game,
            "number_of_confirmed_players": number_of_confirmed_players,
            "cancelled_with_substitutes": cancelled_with_substitutes,
            "booking_history": found_booking_history,
            "status_options": status_options,
            "breadcrumbs": [
                Breadcrumb(reverse("past_games_url"), "Past games"),
                Breadcrumb(reverse("next_games_url"), "Next games"),
                Breadcrumb(
                    reverse("game_details_url", args=[found_game.id]), found_game.when
                ),
            ],
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


@login_required
@require_POST
def game_player_status_update(request, game_id):
    found_game = get_object_or_404(Game, id=game_id)
    play_slot_keys = [key for key in request.POST if key.startswith("play_slot_")]
    if not play_slot_keys:
        return redirect("game_details_url", game_id=game_id)

    changed_key = play_slot_keys[0]
    player_pk = int(changed_key.replace("play_slot_", ""))

    values = request.POST.getlist(changed_key)
    checked = "on" in values

    player = get_object_or_404(Player, pk=player_pk)
    current_booking = player_helper.get_latest_booking_for_game(player, found_game)
    current_status = current_booking.status if current_booking else None

    if current_status == PlayerStatus.PLANNED:
        new_status = PlayerStatus.PLANNED if checked else PlayerStatus.CANCELLED
    elif current_status == PlayerStatus.CANCELLED:
        new_status = PlayerStatus.PLANNED if checked else PlayerStatus.CANCELLED
    elif current_status == PlayerStatus.RESERVED:
        new_status = PlayerStatus.CONFIRMED if checked else PlayerStatus.RESERVED
    elif current_status == PlayerStatus.CONFIRMED:
        new_status = PlayerStatus.CONFIRMED if checked else PlayerStatus.RESERVED
    else:
        new_status = current_status

    if current_status != new_status:
        BookingHistoryForGame.objects.create(
            player=player,
            game=found_game,
            status=new_status,
            creation_date=timezone.now(),
        )
        send_player_status_update_email(player, found_game, new_status)
        send_player_status_update_email_to_admins(player, found_game, new_status)

    return redirect("game_details_url", game_id=game_id)


@login_required
def all_players(request):
    filter_name = request.GET.get("name", "").strip()
    status = request.GET.get("status")

    stat_counts = Player.objects.aggregate(
        total_players=Count("id"),
        permanent_players=Count("id", filter=Q(role=Player.ROLE_PERMANENT)),
        active_players=Count("id", filter=Q(role=Player.ROLE_ACTIVE)),
        inactive_players=Count("id", filter=Q(role=Player.ROLE_INACTIVE)),
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
    user = player.user
    if request.method == "POST":
        new_username = request.POST.get("username")
        if (
            User.objects.filter(username=new_username)
            .exclude(id=player.user.id)
            .exists()
        ):
            messages.error(request, "This login already exists.")
            return render(
                request,
                "games/player_details.html",
                {"player": player, "form": ..., "error": True},
            )

        user.username = new_username
        user.first_name = request.POST.get("first_name", "")
        user.last_name = request.POST.get("last_name", "")
        user.email = request.POST.get("email", "")
        user.save()

        player.mobile_number = request.POST.get("mobile_number", "")
        player.role = request.POST.get("role", "")
        player.save()

        return redirect("all_players_url")

    return render(
        request,
        "games/player_details.html",
        {
            "player": player,
            "breadcrumbs": [
                Breadcrumb(reverse("all_players_url"), "All Players"),
                Breadcrumb(
                    reverse("player_details_url", args=[player.id]), player.user
                ),
            ],
        },
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_player(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        mobile_number = request.POST.get("mobile_number", "").strip()
        role = request.POST.get("role", Player.ROLE_ACTIVE)

        if not username or not email or not mobile_number:
            messages.error(request, "Username, email and mobile number are required.")
        else:
            try:
                user = User.objects.create_user(username=username, email=email)
                user.first_name = first_name
                user.last_name = last_name
                user.full_clean()
                user.save()

                player = Player(user=user, mobile_number=mobile_number, role=role)
                player.save()

                messages.success(
                    request, f"Player '{username}' It has been added successfully."
                )
                return redirect("all_players_url")

            except IntegrityError:
                messages.error(request, "A user with that name already exists.")
            except ValidationError as e:
                errors = "; ".join([str(err) for err in e.messages])
                messages.error(request, f"Error in the form: {errors}")
            except Exception as e:
                messages.error(request, f"An unexpected error has occurred: {e}")

        return redirect("all_players_url")
    context = {
        "role_choices": Player.ROLE_CHOICES,
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
    found_booking_history = BookingHistoryForGame.objects.all().order_by("-id")
    paginator = Paginator(found_booking_history, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "games/booking_history.html",
        {"booking_history": page_obj},
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_game(request):
    if request.method == "POST":
        game = Game.objects.create(
            when=datetime.strptime(request.POST.get("when", ""), "%Y-%m-%d"),
            status=request.POST.get("status", Game.PLANNED),
            description=request.POST.get("description", ""),
        )
        if request.POST.get("set_players"):
            permanent_players = Player.objects.filter(role=Player.ROLE_PERMANENT)
            active_players = Player.objects.filter(role=Player.ROLE_ACTIVE)

            for player in permanent_players:
                BookingHistoryForGame.objects.create(
                    game=game, player=player, status=PlayerStatus.PLANNED
                )

            for player in active_players:
                BookingHistoryForGame.objects.create(
                    game=game, player=player, status=PlayerStatus.RESERVED
                )

            psm_list = PlayerStatus.objects.all().order_by("date_start")
            game_date = game.when.date() if hasattr(game.when, "date") else game.when

            for psm in psm_list:
                if psm.date_start <= game_date <= psm.date_end:
                    if psm.status == PlayerStatus.RESTING:
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
                                    PlayerStatus.PLANNED,
                                    PlayerStatus.CANCELLED,
                                ]:
                                    new_status = PlayerStatus.CANCELLED
                                elif current_status_key in [
                                    PlayerStatus.CONFIRMED,
                                    PlayerStatus.RESERVED,
                                ]:
                                    new_status = PlayerStatus.RESERVED
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
            "role_choices": Game.STATUS_CHOICES,
        },
    )


@login_required
def add_absence(request):
    players = Player.objects.all()
    status = PlayerStatus.objects.all().order_by("-id")
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

            resting_status_key = PlayerStatus.RESTING

            for game in games_in_range:
                latest_booking = (
                    BookingHistoryForGame.objects.filter(player=player, game=game)
                    .order_by("-creation_date")
                    .first()
                )

                if status == resting_status_key and latest_booking:
                    current_status_key = latest_booking.status
                    if current_status_key in [
                        PlayerStatus.PLANNED,
                        PlayerStatus.CANCELLED,
                    ]:
                        new_status = PlayerStatus.CANCELLED
                    elif current_status_key in [
                        PlayerStatus.CONFIRMED,
                        PlayerStatus.RESERVED,
                    ]:
                        new_status = PlayerStatus.RESERVED
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
            "status_choices": PlayerStatus.STATUS_CHOICES,
            "status": status_page_obj,
        },
    )
