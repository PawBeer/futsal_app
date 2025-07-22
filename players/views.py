from django.shortcuts import render

from .models import Player
from django.db.models import Avg, Min, Max, Count
from django.urls import reverse

# Create your views here.

class Breadcrumb:
    def __init__(self, path, label):
        self.path = path
        self.label = label

def all_players(request):
    found_players = Player.objects.all()
    found_players_aggregation = found_players.aggregate(
        Count('id')
    )
    return render(request, 'players/all_players.html', {
        'players': found_players,
        'details': found_players_aggregation
    })

def player_details(request, player_id):
    found_player = Player.objects.get(id=player_id)
    return render(request, 'players/player_details.html', {
        "player": found_player,
        "breadcrumbs": [
            Breadcrumb(reverse('all_players_url'), 'All Players'),
            Breadcrumb(reverse('player_details_url', args=[found_player.id]), found_player.name),
        ]
    })