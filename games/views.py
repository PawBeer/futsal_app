from datetime import datetime
from django.shortcuts import render
from .models import Game
from django.urls import reverse

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
            Breadcrumb(reverse('next_games_url'), 'Next games'),
            Breadcrumb(reverse('past_games_url'), 'Past games'),
            Breadcrumb(reverse('game_details_url', args=[found_game.id]), found_game.when),
        ],
    })