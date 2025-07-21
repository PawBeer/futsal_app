from datetime import datetime

from django.shortcuts import render

from .models import Game


# Create your views here.
def next_games(request):
    found_games = Game.objects.filter(when__gte=datetime.today()).order_by('when').all()
    return render(request, 'games/next_games.html', {'games': found_games})

def past_games(request):
    found_games = Game.objects.filter(when__lt=datetime.today()).order_by('-when').all()
    return render(request, 'games/past_games.html', {'games': found_games})
def game_details(request, game_id):
    found_game = Game.objects.get(id=game_id)
    return render(request, 'games/game_details.html', {"game": found_game})