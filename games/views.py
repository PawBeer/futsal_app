from datetime import datetime
from django.shortcuts import render
from .models import Game, BookingHistoryForGame
from django.urls import reverse
from .models import Player
from django.db.models import Avg, Min, Max, Count, Q


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


def game_details(request, game_id):
    found_game = Game.objects.get(id=game_id)
    return render(request, 'games/game_details.html', {
        "game": found_game,
        "breadcrumbs": [
            Breadcrumb(reverse('past_games_url'), 'Past games'),
            Breadcrumb(reverse('next_games_url'), 'Next games'),
            Breadcrumb(reverse('game_details_url', args=[found_game.id]), found_game.when),
        ],
    })

def all_players(request):
    found_players = Player.objects.all()
    found_players_aggregation = found_players.aggregate(
        total_players = Count('id'),
        permanent_players=Count('id', filter=Q(role='Permanent')),
        active_players=Count('id', filter=Q(role='Active')),
        inactive_players=Count('id', filter=Q(role='Inactive')),
    )
    return render(request, 'games/all_players.html', {
        'players': found_players,
        'details': found_players_aggregation
    })


def player_details(request, player_id):
    found_player = Player.objects.get(id=player_id)
    return render(request, 'games/player_details.html', {
        "player": found_player,
        "breadcrumbs": [
            Breadcrumb(reverse('all_players_url'), 'All Players'),
            Breadcrumb(reverse('player_details_url', args=[found_player.id]), found_player.name),
        ]
    })

def booking_history(request):
    found_booking_history = BookingHistoryForGame.objects.all()
    return render(request, 'games/booking_history.html', {'booking_history': found_booking_history})
