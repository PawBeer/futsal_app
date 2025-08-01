from datetime import datetime
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, BookingHistoryForGame, User, Player, PlayerStatus
from django.urls import reverse
from .models import Player
from django.db.models import Avg, Min, Max, Count, Q
from django.views import View
from .forms import PlayerForm, GameForm


class Breadcrumb:
    def __init__(self, path, label):
        self.path = path
        self.label = label


# Create your views here.
def next_games(request):
    found_games = Game.objects.filter(when__gte=datetime.today()).order_by('when').all()
    return render(request, 'games/next_games.html', {'games': found_games})


def past_games(request):
    found_games = Game.objects.filter(when__lt=datetime.today()).order_by('-when').all()
    return render(request, 'games/past_games.html', {'games': found_games})


@login_required
def game_details(request, game_id):
    found_game = get_object_or_404(Game, id=game_id)
    players_for_game = Player.objects.filter(status_history__game=found_game).order_by('user__username').distinct()

    player_status_planned = PlayerStatus.objects.get(player_status='planned')
    player_status_cancelled = PlayerStatus.objects.get(player_status='cancelled')

    latest_bookings = {
        player.pk: player.get_latest_booking_for_game(found_game)
        for player in players_for_game
    }

    if request.method == 'POST':
        for player in players_for_game:
            checkbox_name = f'play_slot_{player.pk}'

            if checkbox_name in request.POST:
                BookingHistoryForGame.objects.create(
                    player=player,
                    game=found_game,
                    player_status=player_status_planned,
                    creation_date=timezone.now(),
                )
            else:
                BookingHistoryForGame.objects.create(
                    player=player,
                    game=found_game,
                    player_status=player_status_cancelled,
                    creation_date=timezone.now(),
                )

        return redirect('game_details_url', game_id=found_game.id)

    planned_players_for_game = [
        player for player in players_for_game
        if latest_bookings[player.pk] and latest_bookings[player.pk].player_status == player_status_planned
    ]

    cancelled_players_for_game = [
        player for player in players_for_game
        if latest_bookings[player.pk] and latest_bookings[player.pk].player_status == player_status_cancelled
    ]

    number_of_confirmed_players = len(planned_players_for_game)
    found_booking_history = BookingHistoryForGame.objects.filter(game=found_game)

    return render(request, 'games/game_details.html', {
        "game": found_game,
        "players": players_for_game,
        "latest_bookings": latest_bookings,
        "planned_players_for_game": planned_players_for_game,
        "cancelled_players_for_game": cancelled_players_for_game,
        "number_of_confirmed_players": number_of_confirmed_players,
        "booking_history": found_booking_history,
        "breadcrumbs": [
            Breadcrumb(reverse('past_games_url'), 'Past games'),
            Breadcrumb(reverse('next_games_url'), 'Next games'),
            Breadcrumb(reverse('game_details_url', args=[found_game.id]), found_game.when),
        ],
    })


def all_players(request):
    filter_name = request.GET.get('name', '').strip()
    status = request.GET.get('status')

    stat_counts = Player.objects.aggregate(
        total_players=Count('id'),
        permanent_players=Count('id', filter=Q(role='Permanent')),
        active_players=Count('id', filter=Q(role='Active')),
        inactive_players=Count('id', filter=Q(role='Inactive')),
    )

    players = Player.objects.all()
    if filter_name and len(filter_name) > 1:
        players = players.filter(
            Q(user__first_name__icontains=filter_name) |
            Q(user__last_name__icontains=filter_name) |
            Q(user__username__icontains=filter_name)
        )
    if status == 'permanent':
        players = players.filter(role='Permanent')
    elif status == 'active':
        players = players.filter(role='Active')
    elif status == 'inactive':
        players = players.filter(role='Inactive')

    # Pass both stat_counts and players to the template
    return render(request, 'games/all_players.html', {
        'filter': filter_name,
        'players': players,
        'details': stat_counts,
        'status': status,
    })


@login_required
def player_details(request, player_id):
    found_player = get_object_or_404(Player, id=player_id)
    return render(request, 'games/player_details.html', {
        "player": found_player,
        "breadcrumbs": [
            Breadcrumb(reverse('all_players_url'), 'All Players'),
            Breadcrumb(reverse('player_details_url', args=[found_player.id]), found_player.user),
        ]
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_player(request):
    if request.method == 'POST':
        Player.objects.create(
            name=request.POST['name'],
            surname=request.POST['surname'],
            email=request.POST['email'],
            mobile_number=request.POST['mobile_number'],
            role=request.POST['role']
        )
        return redirect('all_players_url')
    return render(request, 'games/add_player.html')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_player_with_form(request):
    return render(request, 'games/add_player_with_form.html')


@login_required()
def booking_history(request):
    found_booking_history = BookingHistoryForGame.objects.all()
    return render(request, 'games/booking_history.html', {'booking_history': found_booking_history})


class AddPlayerView(View):
    def get(self, request):
        form = PlayerForm()
        return render(request, 'games/add_player_with_form.html', {
            'form': form
        })

    @user_passes_test(lambda u: u.is_superuser)
    def post(self, request):
        pass


class AddGameView(View):
    def get(self, request):
        form = GameForm()
        return render(request, 'games/add_game_with_form.html', {
            'form': form
        })

    @user_passes_test(lambda u: u.is_superuser)
    def post(self, request):
        form = GameForm(request.POST)
        logged_user = request.user
        if form.is_valid():
            game = form.save(commit=False)
            game.when = datetime.today()
            game.save()
            form.save_m2m()

            return redirect('game_details_url', game.id)
