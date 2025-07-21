from django.shortcuts import render

from .models import Game


# Create your views here.
def all_games(request):
    found_games = Game.objects.all()
    return render(request, 'games/games_all.html', {'games': found_games})

def game_details(request, game_id):
    found_game = Game.objects.get(id=game_id)
    return render(request, 'games/game_details.html', {"game": found_game})