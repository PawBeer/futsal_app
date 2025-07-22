from django.shortcuts import render

from .models import Player
from django.db.models import Avg, Min, Max, Count

# Create your views here.
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
    return render(request, 'players/player_details.html', {"player": found_player})